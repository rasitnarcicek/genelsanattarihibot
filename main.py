from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest
import logging
import sqlite3
import json
import time
import os

# --- Temel Yapılandırma ---

# Botun işlemlerini ve hatalarını takip etmek için loglama (kayıt tutma) ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ÖNEMLİ: 'TOKEN' yazan yeri kendi Bot API Token'ınız ile değiştirin!
TOKEN = '7637232124:AAFEttWDFijHYXbNdp4ZZGbxfQ3I85pY-xE' 

# ÖNEMLİ: Geri bildirim almak için kendi Telegram Kullanıcı ID'niz ile değiştirin.
# Geri bildirim özelliğini kullanmak istemiyorsanız, bu değeri 0 olarak bırakabilirsiniz.
FEEDBACK_ADMIN_ID = 946918816 

# --- Quiz Ayarları ---
QUIZ_LENGTH = 10 # Bir quiz oturumunun kaç sorudan oluşacağı

# --- Veritabanı Yardımcı Fonksiyonları ---

def get_db_connection():
    """SQLite veritabanına bir bağlantı döndürür."""
    return sqlite3.connect('art_history_quiz.db')

def setup_database_on_startup():
    """
    Bot başladığında gerekli veritabanı tablolarının mevcut olmasını sağlar.
    Bu fonksiyonu her bot başlangıcında çalıştırmak güvenlidir.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # questions tablosu: Tüm quiz sorularını saklar.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            image_path TEXT,
            answer_type TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            options TEXT,
            explanation TEXT,
            topic TEXT,
            difficulty INTEGER
        )
    ''')
    # users tablosu: Kullanıcı bilgilerini ve mevcut durumlarını saklar.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            current_question_id INTEGER,
            state TEXT,
            FOREIGN KEY (current_question_id) REFERENCES questions(id)
        )
    ''')
    # user_answers tablosu: İstatistikler için her cevabı kaydeder.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT,
            is_correct BOOLEAN NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            answer_time_seconds INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Veritabanı tabloları doğrulandı veya oluşturuldu.")

# --- Durum Yönetimi & Ana Mantık ---

async def update_user_state_and_question(context: ContextTypes.DEFAULT_TYPE, user_id: int, state: str, question_id: int = None, username: str = None) -> None:
    """Kullanıcının durumunu ve mevcut soru ID'sini veritabanında günceller."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if username is None:
        try:
            chat_info = await context.bot.get_chat(user_id)
            username = chat_info.username if chat_info.username else f"id_{user_id}"
        except Exception as e:
            logger.error(f"Kullanıcı ID'si için kullanıcı adı alınamadı: {user_id}. Hata: {e}", exc_info=True)
            username = f"id_{user_id}"
            
    cursor.execute("INSERT OR REPLACE INTO users (id, username, state, current_question_id) VALUES (?, ?, ?, ?)",
                   (user_id, username, state, question_id))
    conn.commit()
    conn.close()
    logger.debug(f"Kullanıcı {user_id} veritabanı durumu '{state}', Soru ID: {question_id} olarak güncellendi.")

async def check_answer(question_id: int, user_answer: str, user_id: int, start_time: float) -> tuple[bool, str]:
    """Kullanıcının cevabını doğru olanla karşılaştırır ve veritabanına kaydeder."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT correct_answer, explanation FROM questions WHERE id = ?", (question_id,))
    question_info = cursor.fetchone()

    if not question_info:
        logger.error(f"check_answer: ID'si {question_id} olan soru veritabanında bulunamadı.")
        conn.close()
        return False, "Bu soru veritabanında bulunamadı."

    correct_answer, explanation = question_info
    is_correct = (user_answer == correct_answer)
    answer_time_seconds = int(time.time() - start_time) if start_time else None

    try:
        cursor.execute(
            "INSERT INTO user_answers (user_id, question_id, user_answer, is_correct, answer_time_seconds) VALUES (?, ?, ?, ?, ?)",
            (user_id, question_id, user_answer, is_correct, answer_time_seconds)
        )
        conn.commit()
        logger.debug(f"Kullanıcı {user_id} Soru {question_id} için cevabı ('{user_answer}') {'doğru' if is_correct else 'yanlış'} idi. Veritabanına kaydedildi.")
    except Exception as e:
        logger.error(f"Kullanıcı {user_id} için cevap veritabanına kaydedilemedi: {e}", exc_info=True)
    finally:
        conn.close()

    return is_correct, explanation

# --- Komut İşleyicileri ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcı /start komutunu gönderdiğinde yanıt verir."""
    user = update.effective_user
    await update_user_state_and_question(context, user.id, 'main_menu', username=user.username)

    await update.message.reply_html(
        rf"Sanat Tarihi dersine hoş geldin, {user.mention_html()}! "
        "Başlamaya hazır olduğunda /soru komutunu gönder."
    )

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcıya rastgele bir sanat tarihi sorusu gönderir."""
    user_id = update.effective_user.id
    logger.debug(f"ask_question fonksiyonu kullanıcı {user_id} için çağrıldı.")

    if user_id not in context.user_data:
        context.user_data[user_id] = {}

    force_reset = context.user_data[user_id].pop('force_quiz_reset', False)
    is_new_command = update.message and update.message.text == "/soru"
    
    questions_answered = context.user_data[user_id].get('current_quiz_questions_answered', 0)

    if questions_answered == 0 or force_reset or is_new_command:
        logger.debug(f"Kullanıcı {user_id} quizi başlatıyor veya yeniden başlatıyor. Sayaçlar sıfırlanıyor.")
        context.user_data[user_id].update({
            'current_quiz_questions_answered': 0,
            'current_quiz_correct_answers': 0,
            'current_quiz_start_time': time.time(),
            'start_time': time.time()
        })
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, text, image_path, options FROM questions ORDER BY RANDOM() LIMIT 1")
    question_data = cursor.fetchone()
    conn.close()

    if not question_data:
        logger.warning(f"Kullanıcı {user_id} için veritabanında soru bulunamadı. Lütfen önce seed_db.py dosyasını çalıştırın.")
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text="Üzgünüm, şu anda mevcut bir soru yok.")
        return

    question_id, question_text, image_path, options_json = question_data
    options = json.loads(options_json) if options_json else []

    await update_user_state_and_question(context, user_id, 'waiting_for_answer', question_id)

    keyboard = []
    for option_text in options:
        option_letter = option_text.split(')')[0].strip()
        keyboard.append([InlineKeyboardButton(option_text, callback_data=f"select_option_{option_letter}")])
    
    keyboard.append([InlineKeyboardButton("Cevabı Onayla", callback_data="submit_answer")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    current_q_count = context.user_data[user_id].get('current_quiz_questions_answered', 0) + 1
    question_display_text = f"**Soru {current_q_count}/{QUIZ_LENGTH}:**\n" + question_text

    sent_message = None
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as photo_file:
                sent_message = await context.bot.send_photo(
                    chat_id=user_id, photo=photo_file, caption=question_display_text,
                    reply_markup=reply_markup, parse_mode='Markdown'
                )
        else:
            if image_path:
                logger.warning(f"Resim belirtilen yolda bulunamadı: {image_path}. Soru sadece metin olarak gönderiliyor.")
            sent_message = await context.bot.send_message(
                chat_id=user_id, text=question_display_text,
                reply_markup=reply_markup, parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Kullanıcıya ({user_id}) soru gönderilemedi: {e}", exc_info=True)
        await context.bot.send_message(chat_id=user_id, text="Üzgünüm, soru gönderilirken bir hata oluştu. Lütfen tekrar dene.")
        return

    if sent_message:
        context.user_data[user_id]['last_question_message_id'] = sent_message.message_id
        logger.info(f"Soru ID {question_id}, kullanıcı {user_id}'e gönderildi. Mesaj ID: {sent_message.message_id}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bilinmeyen komutları veya metin mesajlarını işler."""
    if update.message and update.message.text.startswith('/'):
        await update.message.reply_text("Üzgünüm, bu komutu anlamadım.")
    else:
        await update.message.reply_text("Şu anda bir cevap beklemiyorum. Yeni bir quiz başlatmak için /soru yaz.")

# --- Callback Query (Buton Tıklama) İşleyicileri ---

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tüm inline buton tıklamaları için ana yönlendiricidir."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    try:
        await query.answer()
    except BadRequest:
        logger.warning(f"Callback query ({query.id}) zaten cevaplanmış.")
    except Exception as e:
        logger.error(f"Kullanıcı {user_id} için callback query cevaplanamadı: {e}")

    # --- Gelen callback verisine göre ilgili fonksiyona yönlendir ---
    
    if data == "start_new_quiz":
        await query.edit_message_text("Yeni quiz başlatılıyor...")
        context.user_data[user_id]['force_quiz_reset'] = True
        await ask_question(update, context)
        return

    if data == "review_wrong_answers" or data == "review_wrong_answers_list":
        if query.message:
            await query.edit_message_text("Yanlış cevapların getiriliyor...", reply_markup=None)
        await review_wrong_answers(update, context)
        return
        
    if data.startswith("review_wrong_detail_"):
        await handle_wrong_question_review_detail(update, context)
        return
        
    if data in ["confirm_reset", "cancel_reset"]:
        await handle_reset_confirmation(update, context)
        return

    # --- Ana Quiz Cevaplama Mantığı ---
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_question_id, state FROM users WHERE id = ?", (user_id,))
    user_db_info = cursor.fetchone()
    conn.close()

    if not user_db_info or user_db_info[1] != 'waiting_for_answer' or user_db_info[0] is None:
        logger.warning(f"Kullanıcı {user_id} bir quiz butonuna tıkladı ama 'waiting_for_answer' durumunda değil.")
        await query.edit_message_text("Şu anda bir soru yanıtlamıyorsun veya bu soru zaten yanıtlandı. Yeni bir quiz için /soru yaz.")
        return

    question_id = user_db_info[0]

    # Seçenek seçimi
    if data.startswith("select_option_"):
        selected_option_letter = data.split('_')[2]
        selected_options = context.user_data[user_id].setdefault("selected_options", [])
        
        if selected_option_letter.upper() == 'F':
            if 'F' in selected_options:
                selected_options.clear()
            else:
                selected_options.clear()
                selected_options.append('F')
        else:
            if 'F' in selected_options:
                selected_options.remove('F')
            
            if selected_option_letter in selected_options:
                selected_options.remove(selected_option_letter)
            else:
                selected_options.append(selected_option_letter)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT text, options FROM questions WHERE id = ?", (question_id,))
        q_text, q_options_json = cursor.fetchone()
        conn.close()
        original_options = json.loads(q_options_json)

        updated_keyboard = []
        for opt_text in original_options:
            opt_letter = opt_text.split(')')[0].strip()
            btn_text = "✅ " + opt_text if opt_letter in selected_options else opt_text
            updated_keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"select_option_{opt_letter}")])
        
        updated_keyboard.append([InlineKeyboardButton("Cevabı Onayla", callback_data="submit_answer")])
        
        current_q_count = context.user_data[user_id].get('current_quiz_questions_answered', 0) + 1
        q_text_edit = f"**Soru {current_q_count}/{QUIZ_LENGTH}:**\n{q_text}"
        selected_str = ", ".join(sorted(selected_options)) or "Hiçbiri"
        full_caption = f"{q_text_edit}\n\nSeçilen: *{selected_str}*"

        try:
            last_message_id = context.user_data[user_id].get('last_question_message_id')
            if query.message.photo:
                await context.bot.edit_message_caption(chat_id=user_id, message_id=last_message_id, caption=full_caption, reply_markup=InlineKeyboardMarkup(updated_keyboard), parse_mode='Markdown')
            else:
                await context.bot.edit_message_text(chat_id=user_id, message_id=last_message_id, text=full_caption, reply_markup=InlineKeyboardMarkup(updated_keyboard), parse_mode='Markdown')
        except BadRequest as e:
            if "message is not modified" not in str(e):
                 logger.error(f"Seçenek seçimi sırasında mesaj düzenlenemedi: {e}")
        return

    # Cevap gönderimi
    if data == "submit_answer":
        user_answer_options = sorted(context.user_data[user_id].get("selected_options", []))
        if not user_answer_options:
            await query.answer("Lütfen en az bir seçenek belirle.", show_alert=True)
            return

        user_answer_str = ",".join(user_answer_options)
        start_time = context.user_data[user_id].get('start_time')
        
        is_correct, explanation = await check_answer(question_id, user_answer_str, user_id, start_time)
        
        context.user_data[user_id]['current_quiz_questions_answered'] += 1
        if is_correct:
            context.user_data[user_id]['current_quiz_correct_answers'] += 1

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT correct_answer, text FROM questions WHERE id = ?", (question_id,))
        correct_ans_db, q_text = cursor.fetchone()
        conn.close()

        result_message = "Doğru! 🎉" if is_correct else f"Yanlış. Doğru cevap: *{correct_ans_db}*"
        if explanation:
            result_message += f"\n\nAçıklama:\n{explanation}"

        full_response_text = f"**Soru:** {q_text}\n\n{result_message}"
        
        try:
            last_message_id = context.user_data[user_id].get('last_question_message_id')
            if query.message.photo:
                await context.bot.edit_message_caption(chat_id=user_id, message_id=last_message_id, caption=full_response_text, reply_markup=None, parse_mode='Markdown')
            else:
                await context.bot.edit_message_text(chat_id=user_id, message_id=last_message_id, text=full_response_text, reply_markup=None, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Cevap gönderimi sırasında mesaj düzenlenemedi: {e}")

        await update_user_state_and_question(context, user_id, 'main_menu')
        context.user_data[user_id].pop("selected_options", None)
        context.user_data[user_id]['start_time'] = time.time()

        if context.user_data[user_id]['current_quiz_questions_answered'] >= QUIZ_LENGTH:
            await show_quiz_summary(update, context)
        else:
            await ask_question(update, context)
        return
        
# --- Ek Özellik İşleyicileri ---

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcının kişisel quiz istatistiklerini gösterir."""
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), AVG(answer_time_seconds) FROM user_answers WHERE user_id = ?", (user_id,))
    total, correct, avg_time = cursor.fetchone()
    conn.close()

    total = total or 0
    correct = correct or 0
    wrong = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    avg_time_str = f"{avg_time:.2f} saniye" if avg_time else "Mevcut Değil"

    stats_message = (
        f"**Quiz İstatistiklerin:**\n\n"
        f"Toplam Cevaplanan Soru: *{total}*\n"
        f"✅ Doğru Cevaplar: *{correct}*\n"
        f"❌ Yanlış Cevaplar: *{wrong}*\n"
        f"🎯 Başarı Oranı: *{accuracy:.2f}%*\n"
        f"⏱️ Ortalama Cevap Süresi: *{avg_time_str}*\n"
    )
    await update.message.reply_text(stats_message, parse_mode='Markdown')

async def review_wrong_answers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcının yanlış cevapladığı son 10 soruyu listeler."""
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT q.id, q.text, q.correct_answer, ua.user_answer
        FROM user_answers ua JOIN questions q ON ua.question_id = q.id
        WHERE ua.user_id = ? AND ua.is_correct = 0
        ORDER BY ua.timestamp DESC LIMIT 10
    """, (user_id,))
    wrong_questions = cursor.fetchall()
    conn.close()

    if not wrong_questions:
        message_text = "Henüz yanlış cevapladığın bir soru yok. Tebrikler!"
        chat_id = update.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=message_text)
        return

    response_message = "**Son 10 Yanlış Cevabın:**\n\n"
    keyboard = []
    for i, (q_id, q_text, correct_ans, user_ans) in enumerate(wrong_questions):
        summary = q_text.split('\n')[0][:50] + "..."
        response_message += f"*{i+1}. {summary}*\n  Senin cevabın: `{user_ans}`, Doğru: `{correct_ans}`\n"
        keyboard.append([InlineKeyboardButton(f"Soruyu İncele {i+1}", callback_data=f"review_wrong_detail_{q_id}")])

    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=response_message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def handle_wrong_question_review_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Belirli bir yanlış cevaplanmış sorunun tam detaylarını gösterir."""
    query = update.callback_query
    user_id = query.from_user.id
    question_id = int(query.data.split('_')[3])

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Soru detaylarını al
    cursor.execute("SELECT text, correct_answer, explanation, image_path FROM questions WHERE id = ?", (question_id,))
    q_data = cursor.fetchone()
    
    # GÜNCELLEME: Kullanıcının bu soruya verdiği son yanlış cevabı da al
    cursor.execute(
        "SELECT user_answer FROM user_answers WHERE user_id = ? AND question_id = ? AND is_correct = 0 ORDER BY timestamp DESC LIMIT 1",
        (user_id, question_id)
    )
    user_answer_data = cursor.fetchone()
    
    conn.close()

    if not q_data:
        await query.edit_message_text("Üzgünüm, bu sorunun detayları bulunamadı.")
        return

    q_text, correct_answer, explanation, image_path = q_data
    # Kullanıcının cevabı bulunamazsa varsayılan bir metin göster
    user_answer = user_answer_data[0] if user_answer_data else "Bulunamadı"

    # GÜNCELLEME: Mesaj içeriğine kullanıcının cevabını ekle
    detail_message = (
        f"**Soru:** {q_text}\n\n"
        f"**Senin Cevabın:** `{user_answer}`\n"
        f"**Doğru Cevap:** *{correct_answer}*\n\n"
        f"**Açıklama:**\n{explanation}"
    )
    
    # Navigasyon butonlarını ekle
    keyboard = [
        [InlineKeyboardButton("Yanlışlarıma Geri Dön", callback_data="review_wrong_answers_list")],
        [InlineKeyboardButton("Yeni Quiz Başlat", callback_data="start_new_quiz")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(detail_message, reply_markup=reply_markup, parse_mode='Markdown')
    
    if image_path and os.path.exists(image_path):
        # Detay mesajı butonlarla gönderildiği için, resmi ayrı bir mesaj olarak gönder
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=query.from_user.id, photo=photo)


async def reset_statistics_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """İstatistikleri sıfırlamadan önce onay ister."""
    keyboard = [
        [InlineKeyboardButton("Evet, İstatistiklerimi Sıfırla", callback_data="confirm_reset")],
        [InlineKeyboardButton("Hayır, İptal Et", callback_data="cancel_reset")]
    ]
    await update.message.reply_text(
        "Tüm quiz istatistiklerini sıfırlamak istediğinden emin misin? Bu işlem geri alınamaz.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_reset_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """İstatistikleri sıfırlama onayını işler."""
    query = update.callback_query
    if query.data == "confirm_reset":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_answers WHERE user_id = ?", (query.from_user.id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("İstatistiklerin başarıyla sıfırlandı! Yeni bir başlangıç için /soru yaz.")
    else:
        await query.edit_message_text("İşlem iptal edildi. İstatistiklerin güvende.")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Doğru cevaplara göre en iyi 10 kullanıcıyı gösterir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username, 
               SUM(CASE WHEN ua.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
               COUNT(ua.question_id) as total_answered
        FROM users u JOIN user_answers ua ON u.id = ua.user_id
        GROUP BY u.id
        HAVING correct_count > 0
        ORDER BY correct_count DESC, total_answered ASC
        LIMIT 10
    """)
    leaderboard_data = cursor.fetchall()
    conn.close()

    leaderboard_message = "🏆 **Sanat Bilgini Lider Tablosu** 🏆\n\n"
    if not leaderboard_data:
        leaderboard_message += "Lider tablosu boş. İlk doğru cevabı veren sen ol!"
    else:
        for i, (username, correct, total) in enumerate(leaderboard_data):
            leaderboard_message += f"{i+1}. @{username} - *{correct}* doğru cevap ({total} toplam)\n"
    
    await update.message.reply_text(leaderboard_message, parse_mode='Markdown')

async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcı geri bildirimini yöneticiye gönderir."""
    if not FEEDBACK_ADMIN_ID:
        await update.message.reply_text("Geri bildirim özelliği şu anda devre dışı.")
        return

    if not context.args:
        await update.message.reply_text("Lütfen geri bildiriminizi komuttan sonra yazın, örn: /geri_bildirim Bu bot harika!")
        return

    feedback_text = " ".join(context.args)
    user = update.effective_user
    try:
        await context.bot.send_message(
            chat_id=FEEDBACK_ADMIN_ID,
            text=f"**Yeni Geri Bildirim:**\n\nGönderen: @{user.username} (ID: {user.id})\n\nMesaj:\n_{feedback_text}_",
            parse_mode='Markdown'
        )
        await update.message.reply_text("Teşekkürler! Geri bildirimin gönderildi.")
    except Exception as e:
        logger.error(f"Yöneticiye geri bildirim gönderilemedi: {e}", exc_info=True)
        await update.message.reply_text("Üzgünüm, geri bildirimin gönderilirken bir hata oluştu.")

async def show_quiz_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bir quiz oturumu tamamlandıktan sonra bir özet gösterir."""
    user_id = update.effective_user.id
    data = context.user_data.get(user_id, {})
    total_answered = data.get('current_quiz_questions_answered', 0)
    correct = data.get('current_quiz_correct_answers', 0)
    duration = int(time.time() - data.get('current_quiz_start_time', time.time()))
    accuracy = (correct / total_answered * 100) if total_answered > 0 else 0

    summary_message = (
        f"**Quiz Tamamlandı! 🎉**\n\n"
        f"Cevaplanan Soru: *{total_answered}*\n"
        f"✅ Doğru: *{correct}*\n"
        f"❌ Yanlış: *{total_answered - correct}*\n"
        f"🎯 Başarı Oranı: *{accuracy:.2f}%*\n"
        f"⏱️ Geçen Süre: *{duration} saniye*\n\n"
        "Yeni bir quiz başlatmak veya yanlışlarını görmek için aşağıdaki butonları kullanabilirsin."
    )
    
    keyboard = [
        [InlineKeyboardButton("Yeni Quiz Başlat", callback_data="start_new_quiz")],
        [InlineKeyboardButton("Yanlışlarımı İncele", callback_data="review_wrong_answers")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Quiz oturum verilerini temizle
    context.user_data[user_id] = {}

    await context.bot.send_message(
        chat_id=user_id, 
        text=summary_message, 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def main() -> None:
    """Botu başlatır ve komut işleyicilerini ayarlar."""
    application = Application.builder().token(TOKEN).build()

    # Komut işleyicileri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("soru", ask_question))
    application.add_handler(CommandHandler("istatistik", show_statistics))
    application.add_handler(CommandHandler("yanlislarim", review_wrong_answers))
    application.add_handler(CommandHandler("sifirla", reset_statistics_confirmation))
    application.add_handler(CommandHandler("liderler", show_leaderboard))
    application.add_handler(CommandHandler("geri_bildirim", feedback))

    # Tüm buton tıklamaları için ana callback query işleyicisi
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Bilinmeyen komutlar ve metinler için mesaj işleyicileri
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Bot çalışıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    setup_database_on_startup()
    main()
