import sqlite3
import json
import logging
import string
import random # random modülünü ekledik

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def setup_database():
    """Veritabanı bağlantısı kurar ve sorular tablosunu temizleyip yeniden oluşturur."""
    conn = sqlite3.connect('art_history_quiz.db')
    cursor = conn.cursor()
    
    # Her çalıştığında temiz bir başlangıç yapmak için eski soruları siler.
    cursor.execute("DROP TABLE IF EXISTS questions")
    
    # 'donem' ve 'sinav_turu' sütunları ile yeni tablo oluştur
    cursor.execute('''
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            image_path TEXT,
            answer_type TEXT NOT NULL,
            correct_answer TEXT NOT NULL, -- Bu sütun artık şık metnini saklayacak
            options TEXT,
            explanation TEXT,
            donem TEXT,
            sinav_turu TEXT
        )
    ''')
    
    # Diğer tabloların varlığını kontrol et (bunları silmiyoruz)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            current_question_id INTEGER,
            state TEXT,
            FOREIGN KEY (current_question_id) REFERENCES questions(id)
        )
    ''')
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
    logger.info("Veritabanı tabloları kontrol edildi/oluşturuldu.")

def process_question_options(question):
    """
    Her soruya 'F) Hiçbiri' seçeneğini ekler ve şıkları büyük harf A) B) şeklinde yeniden düzenler.
    Ayrıca, açıklaması 'doğru cevap yoktu' anlamına gelen soruların doğru cevabını 'F' olarak ayarlar.
    Son olarak, correct_answer'ı şık harfinden şık metnine dönüştürür.
    Şıkları rastgele karıştırır.
    """
    original_options_list = json.loads(question["options"])
    
    # Mevcut şıklardaki harfleri temizle ve sadece metni al
    cleaned_options_text = [opt[opt.find(')') + 2:] if ')' in opt else opt for opt in original_options_list]
    
    # Eğer 'Hiçbiri' seçeneği yoksa ekle
    if "Hiçbiri" not in cleaned_options_text:
        cleaned_options_text.append("Hiçbiri")

    # Şıkları karıştır
    random.shuffle(cleaned_options_text)

    # Şıkları A) B) C) ... şeklinde yeniden etiketle ve geçici bir harf-metin haritası oluştur
    new_options_with_letters = []
    letter_to_option_map = {}
    for i, opt_text in enumerate(cleaned_options_text):
        current_letter = string.ascii_uppercase[i]
        new_options_with_letters.append(f"{current_letter}) {opt_text}")
        letter_to_option_map[current_letter] = opt_text
    
    question["options"] = json.dumps(new_options_with_letters)

    # Açıklamada "doğru cevap yoktur" veya "bulunmamaktadır" gibi ifadeler varsa,
    # correct_answer'ı "F" olarak ayarla.
    explanation_lower = question["explanation"].lower()
    if any(phrase in explanation_lower for phrase in [
        "seçeneklerde romanesk dönem bulunmamaktadır",
        "seçeneklerde gotik dönemi yer almamaktadır",
        "seçeneklerde bizans dönemi yer almamaktadır",
        "seçeneklerde antik roma dönemi verilmemiştir",
        "seçeneklerde rönesans dönemi verilmemiştir",
        "verilen şıklardan hiçbiri doğru değildir",
        "leonardo da vinci seçenekler arasında yer almamaktadır",
        "verilen sanatçılardan hiçbiri maniyerist dönemin tipik temsilcilerinden değildir",
        "şıklar arasında bu sanatçılar yer almamaktadır",
        "en uygun cevap olan maniyerizm şıklarda yer almadığı için doğru cevap yoktur",
        "verilen seçeneklerde doğru eşleştirme yoktur"
    ]):
        question["correct_answer"] = "Hiçbiri" # Metin olarak "Hiçbiri" olarak ayarla
    
    # Şimdi correct_answer'ı şık harfinden şık metnine dönüştür (eğer daha önce harf olarak ayarlanmışsa)
    # Bu adım, correct_answer zaten metin olarak ayarlandığı için genellikle gereksizdir,
    # ancak orijinal veride harf varsa uyumluluk için tutulmuştur.
    current_correct_answers_texts = question["correct_answer"].split(',')
    
    # Eğer correct_answer hala harf içeriyorsa (eski veriden kalma), bunu metne dönüştür
    # "F" zaten "Hiçbiri" metnine dönüştürüldüğü için bu kontrol daha çok diğer harfler içindir.
    if all(len(ans) == 1 and ans in string.ascii_uppercase for ans in current_correct_answers_texts):
        converted_answers = []
        for ans_letter in current_correct_answers_texts:
            # letter_to_option_map'in güncel şık sırasına göre oluşturulduğunu unutmayın
            # bu nedenle, correct_answer'ı şık metnine dönüştürürken,
            # orijinal şık metinlerini kullanmalıyız, yeni karıştırılmış haritalamayı değil.
            # Bu durum, correct_answer'ın zaten metin olarak saklanması kararını pekiştiriyor.
            # Ancak, eğer doğru cevap hala harf olarak geliyorsa, onu bulmak için tüm seçenekleri kontrol etmeliyiz.
            found_text = None
            for original_opt in original_options_list:
                if original_opt.startswith(ans_letter + ')'):
                    found_text = original_opt[original_opt.find(')') + 2:]
                    break
            if found_text:
                converted_answers.append(found_text)
            else:
                # Eğer harf "F" ise ve "Hiçbiri" metni varsa
                if ans_letter == 'F' and "Hiçbiri" in cleaned_options_text:
                    converted_answers.append("Hiçbiri")
                else:
                    logger.warning(f"Soru metni: '{question['text']}' için geçersiz doğru cevap harfi dönüştürme: {ans_letter}")
                    converted_answers.append(ans_letter) # Fallback
        question["correct_answer"] = ",".join(converted_answers)


    return question

def insert_sample_questions():
    """Veritabanına sadece belirtilen soruları ekler."""
    conn = sqlite3.connect('art_history_quiz.db')
    cursor = conn.cursor()

    questions_to_insert = [
        # --- 2. DÖNEM - GÜNCEL VİZE SORULARI ---
        {
            "text": "1) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans dini mimari yapılarının plan özelliklerine göre verilen isimlerindendir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "C,D",
            "options": json.dumps(["A) Manastır", "B) Narteks", "C) Kubbeli Bazilika", "D) Rotunda", "E) Obelisk"]),
            "explanation": "Kubbeli Bazilika ve Rotunda, Bizans mimarisinde görülen önemli plan tipleridir. Manastır bir yapılar kompleksi, Narteks bir bölüm, Obelisk ise bir anıttır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "2) Aşağıdaki seçenek veya seçeneklerden hangileri Erken Hristiyanlık Dönemi kilise planına göre mimari bölümler için kullanılan terimlerdendir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Transept", "B) Uçan Payanda", "C) Forum", "D) Gül Pencere", "E) Kaburgalı Tonoz"]),
            "explanation": "Transept, Erken Hristiyanlık bazilikalarında ana nefi kesen ve yapıya haç şeklini veren enine koldur. Diğer seçenekler Gotik mimariye aittir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "3) Genellikle kırmızı, mavi ve sarı renklerin kullanıldığı ve dönemi itibariyle duvar resimlerini dahi gölgede bırakan vitray süslemeleri aşağıdaki hangi dönem veya dönemlerde görülmektedir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "D",
            "options": json.dumps(["A) Merovenj", "B) Ottonyen", "C) Karolenj", "D) Gotik", "E) Bizans"]),
            "explanation": "Vitray sanatı en parlak dönemini Gotik mimariyle yaşamıştır. Gotik katedrallerde duvar yüzeyleri incelmiş ve pencerelerin büyümesiyle vitray kullanımı artmıştır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "4) Aşağıdaki seçenek veya seçeneklerden hangisindeki dönemde görülen typanum rölyeflerinde figürler orantısız, uzun ve hareketleri mekanik şekilde betimlenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Karolenj", "B) Bizans", "C) Merovenj", "D) Rönesans", "E) Ottonyen", "F) Hiçbiri"]),
            "explanation": "Soruda tanımlanan üslup, Romanesk dönem kiliselerinin tympanum kabartmalarının karakteristik özelliğidir. Seçeneklerde Romanesk dönem bulunmamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "5) Romanesk dönemde inşa edilen yapılardan hangisi veya hangileri aşağıdaki seçeneklerde doğru olarak yazılmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "E",
            "options": json.dumps(["A) St. Denıs Katedrali", "B) St. Vıtale Kilisesi", "C) St. Mıchael Kilisesi", "D) St. Rıquıer Kilisesi", "E) Pisa"]),
            "explanation": "Pisa Katedrali ve kompleksi, İtalyan Romanesk mimarisinin en tanınmış örneklerindendir. Diğerleri farklı dönemlere aittir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "6) Özellikle dini mimaride rastlanan sivri kemer, kaburgalı tonoz, uçan payanda ve gül pencere gibi yapı elemanları hangi dönem veya dönemlerde en çok karşımıza çıkmaktadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Ottonyen", "B) Bizans", "C) Karolenj", "D) Merovenj", "E) Romanesk", "F) Hiçbiri"]),
            "explanation": "Soruda listelenen yapı elemanları (sivri kemer, kaburgalı tonoz, uçan payanda, gül pencere) hep birlikte Gotik mimarinin ayırt edici özellikleridir. Seçeneklerde Gotik dönemi yer almamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "7) Aşağıdaki isimlerden hangisi veya hangileri Gotik Dönem resim sanatçıları arasındadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Sımon Martini", "B) Leonardo Da Vinci", "C) Brunelleschı", "D) Mıchelangelo", "E) Albertı"]),
            "explanation": "Simone Martini, Uluslararası Gotik üslubun en önemli temsilcilerinden biridir. Diğerleri Rönesans sanatçılarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "8) Yerebatan Sarnıcı, Binbirdirek Sarnıcı gibi profan yapıların inşa edildiği dönem aşağıdakilerden hangisi veya hangileridir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Romanesk", "B) Gotik", "C) Karolenj", "D) Ottonyen", "E) Merovenj", "F) Hiçbiri"]),
            "explanation": "İstanbul'da bulunan Yerebatan Sarnıcı ve Binbirdirek Sarnıcı, Bizans dönemine aittir. Seçeneklerde Bizans dönemi yer almamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "9) Aşağıdaki seçeneklerden hangisi veya hangileri Bizans sanatı içinde İstanbul’da görülen buluntular arasında sayılabilir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,E",
            "options": json.dumps(["A) Çemberlitaş", "B) Villa Capra", "C) Pazzi Şapeli", "D) Palazzo Pitti", "E) Yılanlı Sütun"]),
            "explanation": "Çemberlitaş ve Yılanlı Sütun, İstanbul'daki önemli Bizans anıtlarıdır. Diğerleri İtalya'daki Rönesans yapılarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "10) Evangelist sembolleri aşağıdakilerden hangisi veya hangilerinde doğru verilmiştir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,C",
            "options": json.dumps(["A) Boğa (Luka)", "B) Kartal (Matta)", "C) Aslan (Markos)", "D) Melek (Yuhanna)", "E) Boğa (Markos)"]),
            "explanation": "Doğru eşleştirmeler: Luka → Boğa, Markos → Aslan, Matta → Melek, Yuhanna → Kartal.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "11) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans sanatı içinde İstanbul’da görülen buluntular arasında sayılabilir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,E",
            "options": json.dumps(["A) Çemberlitaş", "B) Villa Capra", "C) Pazzi Şapeli", "D) Palazzo Pitti", "E) Yılanlı Sütun"]),
            "explanation": "Çemberlitaş ve Yılanlı Sütun, İstanbul'daki önemli Bizans anıtlarıdır. Diğerleri İtalya'daki Rönesans yapılarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "12) Kilise ve katedrallerin altında gizli mezar odalarına ne ad verilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "B",
            "options": json.dumps(["A) Transept", "B) Kripta", "C) Nef", "D) Şapel", "E) Narteks"]),
            "explanation": "Kripta, kiliselerin altında yer alan, genellikle kutsal kişilerin mezarlarının bulunduğu yeraltı mezar odasıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "13) Aşağıdaki seçenek veya seçeneklerden hangileri Erken Hristiyanlık dönemi kilise mimari bölümleri için kullanılan isimlerdendir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Transept", "B) Uçan Payanda", "C) Forum", "D) Gül Pencere", "E) Kaburgalı Tonoz"]),
            "explanation": "Transept, Erken Hristiyanlık bazilikalarında ana nefi kesen ve yapıya haç şeklini veren enine koldur. Diğer seçenekler Gotik mimariye aittir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "14) Evangelist sembolleri aşağıdakilerden hangisi veya hangilerinde doğru verilmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Boğa (Matta)", "B) Kartal (Matta)", "C) Aslan (Luka)", "D) Melek (Yuhanna)", "E) Boğa (Markos)", "F) Hiçbiri"]),
            "explanation": "Doğru eşleştirmeler: Matta → Melek, Markos → Aslan, Luka → Boğa, Yuhanna → Kartal. Verilen seçeneklerde doğru eşleştirme yoktur.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "15) Aşağıdaki isimlerden hangisi veya hangileri Gotik dönem resim sanatçıları arasındadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Simon Martini", "B) Leonardo Da Vinci", "C) Brunelleschi", "D) Michelangelo", "E) Alberti"]),
            "explanation": "Simone Martini, Uluslararası Gotik üslubun önemli temsilcisidir. Diğerleri Rönesans sanatçılarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "16) Yerebatan Sarnıcı, Binbirdirek Sarnıcı gibi profan yapıların inşa edildiği dönem aşağıdakilerden hangisi veya hangileridir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Romanesk", "B) Gotik", "C) Karolenj", "D) Ottonyen", "E) Merovenj", "F) Hiçbiri"]),
            "explanation": "İstanbul'daki Yerebatan Sarnıcı ve Binbirdirek Sarnıcı, Bizans İmparatorluğu döneminde inşa edilmiştir. Seçeneklerde Bizans dönemi yoktur.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "17) Genellikle kırmızı, mavi ve sarı renklerin kullanıldığı ve dönemi itibariyle duvar resimlerini dahi gölgede bırakan vitray süslemeleri aşağıdaki hangi dönem veya dönemlerde görülmektedir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "D",
            "options": json.dumps(["A) Merovenj", "B) Ottonyen", "C) Karolenj", "D) Gotik", "E) Romanesk"]),
            "explanation": "Vitray sanatı, en parlak dönemini Gotik mimariyle yaşamıştır. Diğer dönemlerde vitray kullanımı bu kadar baskın ve gelişmiş değildi.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "18) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans dini mimari yapılarının plan özelliklerine göre verilen isimlerindendir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "C,D",
            "options": json.dumps(["A) Manastır", "B) Narteks", "C) Kubbeli Bazilika", "D) Rotunda", "E) Obelisk"]),
            "explanation": "Kubbeli Bazilika ve Rotunda, Bizans mimarisinde görülen önemli plan tipleridir. Diğerleri plan tipi değildir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "19) Romanesk dönemde inşa edilen yapılardan hangisi veya hangileri aşağıdaki seçeneklerde doğru olarak yazılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,E",
            "options": json.dumps(["A) St. Etienne Kilisesi", "B) St. Vitale Kilisesi", "C) St. Michael Kilisesi", "D) St. Riquier Kilisesi", "E) Pisa"]),
            "explanation": "St. Etienne Kilisesi (Caen, Fransa) ve Pisa Katedrali kompleksi, Romanesk mimarinin önemli örneklerindendir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "20) Aşağıdaki seçenek veya seçeneklerden hangisindeki dönemde görülen Typanum rölyeflerinde figürler orantısız, uzun ve hareketleri mekanik şekilde betimlenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Karolenj", "B) Bizans", "C) Merovenj", "D) Rönesans", "E) Ottonyen", "F) Hiçbiri"]),
            "explanation": "Soruda tarif edilen üslup, Romanesk dönem tympanum kabartmalarında görülür. Seçenekler arasında Romanesk dönem bulunmamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "21) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans dini mimari yapılarının plan özelliklerine göre verilen isimlerindendir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "C,D",
            "options": json.dumps(["A) Manastır", "B) Narteks", "C) Kubbeli Bazilika", "D) Rotunda", "E) Obelisk"]),
            "explanation": "'Kubbeli Bazilika' ve 'Rotunda' Bizans mimarisindeki plan tipleridir. Diğerleri plan tipi değildir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "22) Aşağıdaki seçenek veya seçeneklerden hangileri Erken Hristiyanlık dönemi kilise mimari bölümleri için kullanılan isimlerdendir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Transept", "B) Uçan Payanda", "C) Forum", "D) Gül Pencere", "E) Kaburgalı Tonoz"]),
            "explanation": "Transept, Erken Hristiyanlık bazilikalarında haç planı oluşturan enine neftir. Diğerleri Gotik mimari veya Roma mimarisine aittir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "23) Genellikle kırmızı, mavi ve sarı renklerin kullanıldığı ve dönemi itibariyle duvar resimlerini dahi gölgede bırakan vitray süslemeleri aşağıdaki hangi dönem veya dönemlerde görülmektedir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "D",
            "options": json.dumps(["A) Merovenj", "B) Ottonyen", "C) Karolenj", "D) Gotik", "E) Romanesk"]),
            "explanation": "Vitray sanatı en parlak dönemini Gotik mimariyle yaşamıştır. Diğer dönemlerde bu kadar belirleyici bir sanat dalı değildir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "24) Aşağıdaki seçenek veya seçeneklerden hangisindeki dönemde görülen Typanum rölyeflerinde figürler orantısız, uzun ve hareketleri mekanik şekilde betimlenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Karolenj", "B) Bizans", "C) Merovenj", "D) Rönesans", "E) Ottonyen", "F) Hiçbiri"]),
            "explanation": "Figürlerin orantısız ve uzun betimlendiği tympanum rölyefleri Romanesk dönemin karakteristik özelliğidir. Şıklarda Romanesk dönem verilmemiştir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "25) Romanesk dönemde inşa edilen yapılardan hangisi veya hangileri aşağıdaki seçeneklerde doğru olarak yazılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "C,E",
            "options": json.dumps(["A) St. Denis Katedrali", "B) St. Viteale Kilisesi", "C) St. Michael Kilisesi", "D) St. Riquier Kilisesi", "E) Pisa"]),
            "explanation": "St. Michael Kilisesi (Erken Romanesk) ve Pisa Katedrali kompleksi (İtalyan Romanesk) bu döneme aittir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "26) Antik Yunan tapınaklarından bildiğimiz ve Vitruvius’un tanımladığı “Dor”, “İyon” ve “Korint” mimari sistemlerinin yanına aşağıdaki dönemlerin hangisinde veya hangilerinde Alberti’nin tanımladığı “Kompozit” sistem eklenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Gotik", "B) Ottonyen", "C) Bizans", "D) Karolenj", "E) Romanesk", "F) Hiçbiri"]),
            "explanation": "Kompozit ve Toskan sistemlerini klasik düzenlere ekleyen ve teorize edenler Rönesans dönemi mimarlarıdır. Şıklarda Rönesans dönemi verilmemiştir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "27) Aşağıdaki isimlerden hangisi veya hangileri Gotik dönem resim sanatçıları arasındadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Simon Martini", "B) Leonardo Da Vinci", "C) Brunelleschi", "D) Michelangelo", "E) Alberti"]),
            "explanation": "Simone Martini, İtalyan Gotik resminin önemli bir temsilcisidir. Diğerleri Rönesans sanatçılarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "28) Ruccellal Sarayı, Santa Maria Novella, Palazzo Farnese, Laurenziana Kitaplığı gibi yapılar aşağıdaki hangi dönem veya dönemlerde inşa edilmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Romanesk", "B) Gotik", "C) Rönesans", "D) Ottonyen", "E) Bizans"]),
            "explanation": "Listelenen yapıların tamamı Erken ve Yüksek Rönesans dönemlerine ait önemli örneklerdir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "29) Aşağıdaki seçeneklerden hangisi Rönesans dönemi mimarisinde kullanılan bir yapı elemanıdır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Pencere Pervazı", "B) Uçan Payanda", "C) İç İskelesi", "D) Kafes Tonozu", "E) Tartışma Kafesi"]),
            "explanation": "Rönesans mimarisinde simetri ve orantılı pencere elemanları, dolayısıyla pencere pervazları, karakteristik özelliklerdendir. Diğerleri farklı dönemlere aittir veya mimari terim değildir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },
        {
            "text": "30) Aşağıdaki dönem veya dönemlerden hangisinde günümüzdeki apartman anlayışına uygun ilk prototip mimari yapılara rastlanılmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Ottonyen", "B) Gotik", "C) Karolenj", "D) Romanesk", "E) Merolenj", "F) Hiçbiri"]),
            "explanation": "Günümüzdeki apartmanların ilk prototipleri olan çok katlı konut yapıları ('Insula'), Antik Roma dönemine aittir. Şıklarda Antik Roma dönemi verilmemiştir.",
            "donem": "2. Dönem", "sinav_turu": "Vize"
        },

        # --- 2. DÖNEM - FİNAL SORULARI ---
        {
            "text": "1) Aşağıdaki isimlerden hangisi veya hangileri Gotik dönem resim sanatçıları arasındadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) El Greco", "B) Gentile Bellini", "C) Brunelleschi", "D) Albrecht Dürer", "E) Alberti", "F) Hiçbiri"]),
            "explanation": "Soruda listelenen sanatçıların hiçbiri doğrudan Gotik dönem sanatçısı olarak sınıflandırılmaz. Gentile Bellini, Brunelleschi, Albrecht Dürer ve Alberti, Rönesans dönemi sanatçılarıdır. El Greco ise Maniyerizm akımının en önemli temsilcilerindendir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "2) Aşağıdaki sanatçı veya sanatçılardan hangisi Maniyerist sanat akımı içinde değerlendirilir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,D",
            "options": json.dumps(["A) Jacopo Pontormo", "B) El Greco", "C) Leonardo Da Vinci", "D) Parmigianino", "E) Velazquez"]),
            "explanation": "Jacopo Pontormo ve Parmigianino, Maniyerizmin en önemli ve tanımlayıcı İtalyan ustaları arasındadır. El Greco da bu akıma dahil edilebilir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "3) Antik Yunan tapınaklarından bildiğimiz ve Vitruvius’un tanımladığı “Dor“, “İyon“ ve “Korint” mimari sistemlerinin yanına aşağıdaki dönemlerin hangisinde Alberti’nin tanımladığı “Kompozit“ sistem eklenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Gotik", "B) Ottonyen", "C) Rönesans", "D) Karolenj", "E) Romanesk"]),
            "explanation": "Kompozit başlığın teorik olarak tanımlanması ve mimari düzenler arasına yeniden dahil edilmesi Alberti gibi Rönesans teorisyenleri sayesinde olmuştur.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "4) Caravaggio'nun etkisi altında İtalya'da eğitim gören pek çok sanatçı onun sanat yolundan ilerlemiştir. Bunlara 'Caravaggistler' adı verilmiştir. Aşağıdaki sanatçı veya sanatçılardan hangisi bu gruba dahil edilebilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "E",
            "options": json.dumps(["A) Leonardo Da Vinci", "B) Rosso Fiorentino", "C) Michelangelo", "D) Rubens", "E) Georges de La Tour"]),
            "explanation": "Georges de La Tour, Caravaggio'nun dramatik ışık-gölge kullanımını benimseyen Fransız Barok sanatçısıdır ve 'Caravaggistler' akımının en önemli temsilcilerinden biridir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "5) Rucellai Sarayı, Santa Maria Novella, Palazzo Farnese, Laurenziana Kitaplığı gibi yapılar aşağıdaki dönem veya dönemlerde inşa edilmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Romanesk", "B) Gotik", "C) Rönesans", "D) Ottonyen", "E) Bizans"]),
            "explanation": "Listelenen yapıların tamamı İtalya'daki Rönesans mimarisinin başyapıtlarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "6) Aşağıdaki eserlerden hangisi veya hangileri Michelangelo tarafından yapılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,B",
            "options": json.dumps(["A) Pietà heykeli", "B) Davut Heykeli", "C) Perseus ve Medusa", "D) Daphne ve Apollon", "E) Gattamelata"]),
            "explanation": "Pietà ve Davut, Michelangelo'nun en ünlü heykelleri arasındadır. Diğer eserler farklı sanatçılara aittir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "7) Milano'da Santa Maria Della Grazie Kilisesi'nde fresk tekniğinde yapılan 'Son Akşam Yemeği' duvar resmi ile aynı zamanda 'Kayalıklar Bakiresi' ve 'Anna, Kutsal Bakire ve Çocuk' isimli ünlü tabloları bulunan Rönesans Dönemi sanatçı veya sanatçılar aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Tintoretto", "B) Albrecht Dürer", "C) Michelangelo", "D) Rubens", "E) Donatello", "F) Hiçbiri"]),
            "explanation": "Soruda adı geçen üç başyapıtın sanatçısı Leonardo da Vinci'dir. Leonardo da Vinci seçenekler arasında yer almamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "8) 'Gece Devriyesi', 'Anatomi Dersi', 'Müsrif Oğulun Baba Ocağına Dönüşü', 'Musa' gibi tablolar aşağıdaki hangi Barok Dönemi sanatçısı tarafından yapılmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "E",
            "options": json.dumps(["A) Parmigianino", "B) Bellini", "C) Michelangelo", "D) Tiziano", "E) Rembrandt"]),
            "explanation": "'Gece Devriyesi', 'Musa', 'Anatomi Dersi' ve 'Müsrif Oğulun Baba Ocağına Dönüşü' tabloları, Hollandalı Barok ressam Rembrandt'ın en ünlü eserleridir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "9) Aşağıdaki dönem veya dönemlerden hangisinde günümüzdeki apartman anlayışına uygun ilk prototip mimari yapılara rastlanmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Ottonyen", "B) Gotik", "C) Karolenj", "D) Romanesk", "E) Merovenj", "F) Hiçbiri"]),
            "explanation": "Günümüzdeki apartmanlara benzer, çok katlı konut yapılarının (insula) ilk örnekleri Antik Roma dönemine aittir. Verilen şıklarda bu dönem yoktur.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "10) Aşağıdaki mimari eserlerden hangisi veya hangileri Barok Dönem mimarisi içinde önemli bir yere sahiptir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,D",
            "options": json.dumps(["A) Santa Maria della Salute", "B) Pisa", "C) St. Vitale Kilisesi", "D) St Ivo alla Sapienza", "E) Rucellai Sarayı"]),
            "explanation": "Santa Maria della Salute ve Sant'Ivo alla Sapienza, İtalyan Barok mimarisinin en önemli örneklerindendir. Diğerleri farklı dönemlere aittir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "11) Aşağıdaki seçenek veya seçeneklerden hangisindeki dönemde görülen Typanum rölyeflerinde figürler orantısız, uzun ve hareketleri mekanik şekilde betimlenmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Bizans", "B) Rönesans", "C) Ottonyen", "D) Merovenj", "E) Karolenj", "F) Hiçbiri"]),
            "explanation": "Soruda tarif edilen figür özellikleri Romanesk dönemi tympanum rölyeflerinin tipik özelliğidir. Verilen şıklarda Romanesk dönem bulunmamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "12) Aşağıdaki eser veya eserlerden hangisi Barok döneme damgasını vuran heykeltraş Gian Lorenzo Bernini tarafından yapılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "B,C",
            "options": json.dumps(["A) İsa'nın Vaftizi", "B) Daphne ve Apollon", "C) Azize Therasa'nın Vecdi", "D) Pieta", "E) Perseus ve Medusa"]),
            "explanation": "'Daphne ve Apollon' ile 'Azize Therasa'nın Vecdi' Bernini'nin en ünlü ve karakteristik eserlerindendir. Diğerleri farklı sanatçılara aittir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "13) Romanesk dönemde inşa edilen yapılardan hangisi veya hangileri aşağıdaki seçeneklerde doğru olarak yazılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,B",
            "options": json.dumps(["A) Pisa", "B) St. Michael Kilisesi", "C) St. Denis Katedrali", "D) St. Riquier Kilisesi", "E) St. Viteale Kilisesi"]),
            "explanation": "Pisa Katedrali kompleksi İtalyan Romanesk, St. Michael Kilisesi ise Erken Romanesk döneme aittir. Diğerleri farklı dönemlerdendir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "14) Aşağıdakilerden hangisi veya hangileri Bizans Döneminde İstanbul'da inşa edilen profan (dini olmayan) yapılardandır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "D,E",
            "options": json.dumps(["A) Ayasofya Kilisesi", "B) Ravenna Ortodokslar Vaftizhanesi", "C) İstanbul Studios Manastırı", "D) Dikilitaş", "E) Hipodrom"]),
            "explanation": "Dikilitaş ve Hipodrom, Bizans dönemi İstanbul'unda bulunan önemli dini olmayan (profan) yapılardır. Diğerleri dini yapılardır veya İstanbul'da değildir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "15) Resim sanatında anatomik anlamda ölçüye ve dengeye önem verilmeyen, insan figürlerinin boy, boyun ve ellerinin abartılı ölçülerde tuale çizildiği sanat dönemi aşağıdakilerden hangisi veya hangileridir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Bizans", "B) Barok", "C) Romanesk", "D) Rönesans", "E) Karolenj"]),
            "explanation": "Soruda tarif edilen özellikler en belirgin şekilde Romanesk dönem sanatında görülür. Maniyerizm de bu tanıma uyar ancak şıklarda yoktur.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "16) Aşağıdaki eser veya eserlerden hangisi Rönesans dönemi sanatçılarından Raphaello'ya aittir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "B,D",
            "options": json.dumps(["A) Mahşer", "B) Borgo Yangını", "C) Kayalıklar Bakiresi", "D) Atina Okulu", "E) Uyuyan Venüs"]),
            "explanation": "'Borgo Yangını' ve 'Atina Okulu' Raphaello'nun ünlü fresklerindendir. Diğerleri farklı sanatçılara aittir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "17) Hellenistik dönem sanatında çok önemli bir yere sahip olan Yunan mitolojisinde anlatılan 'Lakoon ve Oğulları' heykeline ait konu aşağıdaki Maniyerist sanatçı veya sanatçılardan hangisi tarafından resmedilmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) El Greco", "B) Tintoretto", "C) Parmigianino", "D) Leonardo Da Vinci", "E) Pontormo"]),
            "explanation": "El Greco, 'Laocoön' adlı ünlü bir tablo yapmıştır ve Maniyerist üslubun önemli temsilcilerindendir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "18) Bizans döneminde Rotunda biçiminde inşa edilmiş olan kiliseler aşağıdaki şıklardan hangisi veya hangilerinde doğru yazılmıştır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,B",
            "options": json.dumps(["A) İstanbul Ayia Euphemia Martyrionu", "B) Ravenna St. Viteale Kilisesi", "C) Selanik Hagios Demetrios Kilisesi", "D) İznik Ayasofyası", "E) Modena Katedrali"]),
            "explanation": "Ravenna'daki St. Viteale Kilisesi ve İstanbul'daki Ayia Euphemia Martyrionu'nun merkezi planlı (rotunda benzeri) yapılar olduğu bilinmektedir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "19) Ortaçağ'da Gellone Ayin Kitabı, Lindisfarne İncili ve Codex Amiatinus gibi önemli el yazmaları hangi dönem veya dönemlerde yazılmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Gotik", "B) Romanesk", "C) Barok", "D) Maniyerizm", "E) Rönesans", "F) Hiçbiri"]),
            "explanation": "Bu el yazmaları Erken Orta Çağ'a (İnsular Sanat, Karolenj) aittir ve verilen şıklardan hiçbiri doğru değildir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "20) Barok resim sanatının babası sayılır. Gerçekçi resim anlayışında çoğu birer işçi olan azizleri nasırlı elleri ve çamurlu ayaklarıyla çizmiştir. Eserlerinde mitolojiden de izler görülmektedir. 'Goliat'ın Başını Kesen Genç Davud' önemli eserleri arasındadır. Sözü edilen sanatçı aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "E",
            "options": json.dumps(["A) Velázquez", "B) Rembrandt", "C) Rubens", "D) Leonardo Da Vinci", "E) Caravaggio"]),
            "explanation": "Soruda bahsedilen özellikler (güçlü ışık-gölge, gerçekçilik, sıradan insan gibi azizler) doğrudan Caravaggio'yu işaret etmektedir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "21) Özellikle dini mimaride rastlanan sivri kemer, kaburgalı tonoz, uçan payanda ve gül pencere gibi yapı elemanları hangi dönem veya dönemlerde en çok karşımıza çıkmaktadır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "B",
            "options": json.dumps(["A) Rönesans", "B) Gotik", "C) Ottonyen", "D) Romanesk", "E) Bizans"]),
            "explanation": "Sivri kemer, kaburgalı tonoz, uçan payanda ve gül pencere, Gotik mimarinin en karakteristik yapısal ve estetik elemanlarıdır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "22) Rönesans ve Barok dönemde 'Son Akşam Yemeği /Last Supper' konusunda resim yapan sanatçılar vardır. Aşağıdaki şıklardan hangi sanatçı veya sanatçılar buna örnek verilebilir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,D",
            "options": json.dumps(["A) Tintoretto", "B) Michelangelo", "C) Bronzino", "D) Leonardo Da Vinci", "E) Tiziano"]),
            "explanation": "Leonardo Da Vinci'nin 'Son Akşam Yemeği' (Rönesans) en bilinenidir. Tintoretto da (Geç Rönesans/Maniyerizm) bu konuda önemli bir eser vermiştir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "23) Aşağıdaki sanatçı veya sanatçılardan hangisi Maniyerist dönem sanat anlayışı içinde değerlendirilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Giorgione", "B) Rubens", "C) Uccello", "D) Donatello", "E) Rembrant", "F) Hiçbiri"]),
            "explanation": "Verilen sanatçılardan hiçbiri Maniyerist dönemin tipik temsilcilerinden değildir. Maniyerist sanatçılara örnek olarak Pontormo veya El Greco verilebilirdi.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "24) İtalya'nın Roma kentinde bulunan Vatikan Sistine Şapeli'ndeki tavan süslemelerini yapan önemli Rönesans sanatçısı veya sanatçıları aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "B",
            "options": json.dumps(["A) Caravaggio", "B) Michelangelo", "C) Rubens", "D) Donatello", "E) Leonardo Da Vinci"]),
            "explanation": "Vatikan'daki Sistine Şapeli'nin tavan freskleri Michelangelo tarafından yapılmıştır ve Rönesans sanatının başyapıtlarından kabul edilir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "25) Fransa'da 'Saint Etienne Kilisesi' (Caen), Almanya'da 'Speyer Katedrali', İtalya'da 'Modena ve Pisa Katedrali' gibi yapılar aşağıdaki hangi sanat dönemi veya dönemlerinin en önemli eserleri arasında sayılabilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Rönesans", "B) Karolenj", "C) Ottonyen", "D) Barok", "E) Gotik", "F) Hiçbiri"]),
            "explanation": "Listelenen yapıların tamamı Romanesk dönemi mimarisinin önemli örnekleridir. Verilen şıklarda Romanesk dönem bulunmamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "26) Barok resim sanatının babası sayılır. Gerçekçi resim anlayışında çoğu birer işçi olan azizleri nasırlı elleri ve çamurlu ayaklarıyla çizmiştir. Eserlerinde mitolojiden de izler görülmektedir. “Goliat’ın Başını Kesen Genç Davud” önemli eserleri arasındadır? Sözü edilen sanatçı aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "A",
            "options": json.dumps(["A) Caravaggio", "B) Rubens", "C) Rembrandt", "d) Leonardo Da Vinci", "e) Bellini"]),
            "explanation": "Michelangelo Merisi da Caravaggio, Barok sanatının öncülerinden kabul edilir. Işık-gölge kullanımı ve dramatik gerçekçiliği ile tanınır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "27) Aşağıdaki eser veya eserlerden hangisi Rönesans dönemi sanatçılarından Raphaello’ya aittir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,E",
            "options": json.dumps(["A) Atina Okulu", "B) Kayalıklar Bakiresi", "C) Mahşer", "d) Uyuyan Venüs", "e) Borgo Yangını"]),
            "explanation": "'Atina Okulu' ve 'Borgo Yangını' Raphaello'nun en ünlü eserlerindendir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "28) “Son Akşam Yemeği /Last Supper” konusunda resim yapan sanatçı veya sanatçılar aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "C,D",
            "options": json.dumps(["A) El Greco", "B) Pontormo", "C) Tintoretto", "d) Leonardo Da Vinci", "e) Bronzino"]),
            "explanation": "Leonardo Da Vinci'nin ve Tintoretto'nun 'Son Akşam Yemeği' temalı ünlü eserleri bulunmaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "29) Aşağıdaki sanatçı veya sanatçılardan hangisi Maniyerist dönem sanat anlayışı içinde değerlendirilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Rubens", "B) Donatello", "C) Uccello", "d) Giorgione", "e) Rembrant", "F) Hiçbiri"]),
            "explanation": "Verilen seçeneklerdeki sanatçıların hiçbiri Maniyerist değildir. Maniyerist sanatçılara Pontormo, Rosso Fiorentino, Bronzino gibi isimler örnek verilebilir.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "30) Gentile Bellini aşağıdaki Osmanlı padişahlarından hangisi veya hangilerinin portresini yapmıştır?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Yıldırım Bayezid", "B) Abdülaziz", "C) II. Mehmed", "d) II. Mahmud", "e) Abdülmecid"]),
            "explanation": "Venedikli ressam Gentile Bellini, Sultan II. Mehmed'in (Fatih Sultan Mehmed) daveti üzerine İstanbul'a gelmiş ve padişahın ünlü portresini yapmıştır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "31) Hellenistik dönem sanatında çok önemli bir yere sahip olan Yunan mitolojisinde anlatılan “Lakoon ve Oğulları” heykeline ait konu aşağıdaki Maniyerist sanatçı veya sanatçılardan hangisi tarafından resmedilmiştir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "B",
            "options": json.dumps(["A) Pontormo", "B) El Greco", "C) Leonardo Da Vinci", "d) Parmigianino", "e) Velazquez"]),
            "explanation": "Bu trajik konu, Maniyerist sanatçı El Greco tarafından resmedilmiştir. El Greco'nun 'Laocoön' tablosu, Maniyerist üslubun özelliklerini taşır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "32) Rönesans dönemi eserlerinden Uyuyan Venüs ve Urbino Venüsü isimli iki önemli tablo aşağıdaki şıklarda verilen hangi sanatçı veya sanatçılarla eşleştirilebilir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Rembrant", "B) El Greco", "C) Donatello", "d) Caravagio", "e) Pontormo", "F) Hiçbiri"]),
            "explanation": "'Uyuyan Venüs' Giorgione/Titian'a, 'Urbino Venüsü' ise Titian'a aittir. Şıklarda bu sanatçılar yer almamaktadır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "33) Aşağıdaki eser veya eserlerden hangisi Barok dönem mimari eserlerinden sayılır?",
            "image_path": None, "answer_type": "double_choice", "correct_answer": "A,E",
            "options": json.dumps(["A) Schönbrun Sarayı", "B) Koimesis Kilisesi", "C) Ruccelai Sarayı", "d) Ayasofya Kilisesi", "e) St. Ivo Kilisesi"]),
            "explanation": "Schönbrunn Sarayı (Viyana) ve St. Ivo alla Sapienza Kilisesi (Roma), Barok tarzda inşa edilmiş önemli yapılardır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "34) Anatomik anlamda ölçüye ve dengeye önem verilmeyen, insan figürlerinin boy, boyun ve ellerinin abartılı ölçülerde tuale çizildiği sanat dönemi aşağıdakilerden hangisi veya hangileridir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "F",
            "options": json.dumps(["A) Rönesans", "B) Barok", "C) Romanesk", "d) Karolenj", "e) Bizans", "F) Hiçbiri"]),
            "explanation": "Soruda tarif edilen üslup özellikleri en belirgin şekilde Maniyerizm akımında görülür. En uygun cevap olan Maniyerizm şıklarda yer almadığı için doğru cevap yoktur.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        },
        {
            "text": "35) İtalya’nın Roma kentinde bulunan Vatikan Sistine Şapeli’ndeki tavan süslemelerini yapan önemli Rönesans sanatçısı veya sanatçıları aşağıdakilerden hangisidir?",
            "image_path": None, "answer_type": "single_choice", "correct_answer": "C",
            "options": json.dumps(["A) Leonardo Da Vinci", "B) Caravagio", "C) Michelangelo", "d) Rubens", "e) Donatello"]),
            "explanation": "Vatikan'daki Sistine Şapeli'nin tavan freskleri, Yüksek Rönesans'ın en büyük ustalarından Michelangelo Buonarroti tarafından yapılmıştır.",
            "donem": "2. Dönem", "sinav_turu": "Final"
        }
    ]

    # Her soruyu işle
    processed_questions = [process_question_options(q) for q in questions_to_insert]

    for q in processed_questions:
        cursor.execute(
            "INSERT INTO questions (text, image_path, answer_type, correct_answer, options, explanation, donem, sinav_turu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (q["text"], q["image_path"], q["answer_type"], q["correct_answer"], q["options"], q["explanation"], q["donem"], q["sinav_turu"])
        )
    
    conn.commit()
    conn.close()
    logger.info(f"{len(processed_questions)} adet soru (vize ve final) veritabanına eklendi.")

if __name__ == '__main__':
    setup_database()
    insert_sample_questions()
    print("Veritabanı kurulumu ve tüm vize/final sorularının eklenmesi tamamlandı.")
    print("Artık ana bot dosyasını (main.py) çalıştırabilirsiniz.")
