import sqlite3
import json
import logging

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def setup_database():
    """Veritabanı bağlantısı kurar ve tabloları oluşturur."""
    conn = sqlite3.connect('art_history_quiz.db')
    cursor = conn.cursor()
    # Botun ihtiyaç duyduğu tüm tabloların var olduğundan emin ol
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

def insert_sample_questions():
    """Veritabanına soruları ekler. Eğer soru metni zaten varsa, eklemez."""
    conn = sqlite3.connect('art_history_quiz.db')
    cursor = conn.cursor()

    questions_to_insert = [
        {
            "text": "1) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans sanatı içinde İstanbul’da görülen buluntular arasında sayılabilir?",
            "image_path": None,
            "answer_type": "double_choice",
            "correct_answer": "A,E",
            "options": json.dumps(["A) Çemberlitaş", "B) Villa Capra", "C) Pazzi Şapeli", "D) Palazzo Pitti", "E) Yılanlı Sütun", "F) Hiçbiri"]),
            "explanation": "• Çemberlitaş: İmparator Konstantin'in Roma İmparatorluğu'nun yeni başkenti Konstantinopolis'i (İstanbul) kurduğunda diktirdiği anıtsal sütundur (MS 330). Şehrin önemli Bizans anıtlarındandır.\n• Yılanlı Sütun: Aslen MÖ 5. yüzyılda Yunan şehir devletlerinin Perslere karşı kazandığı zaferin anısına Delfi'ye adanmış tunç bir anıttır. İmparator Konstantin tarafından İstanbul'daki Hipodrom'a getirilmiş ve Bizans dönemi boyunca orada sergilenmiştir. Bu nedenle İstanbul'daki Bizans dönemi buluntuları arasında sayılır.\n• Diğerleri: B) Villa Capra, C) Pazzi Şapeli ve D) Palazzo Pitti, İtalya'da bulunan Rönesans dönemi yapılarıdır.",
            "topic": "Bizans Sanatı",
            "difficulty": 2
        },
        {
            "text": "2) Barok döneminin önde gelen ressamlarından, ışık ve gölgeyi dramatik bir şekilde kullanan sanatçı kimdir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "A",
            "options": json.dumps(["A) Caravaggio", "B) Rembrandt", "C) Vermeer", "D) Rubens", "E) Velázquez", "F) Hiçbiri"]),
            "explanation": "• Caravaggio: Barok resminin en önemli figürlerinden biridir ve dramatik ışık kullanımıyla (chiaroscuro) tanınır.",
            "topic": "Barok Resim",
            "difficulty": 3
        },
        {
            "text": "3) Aşağıdaki seçenek veya seçeneklerden hangileri Erken Hristiyanlık dönemi kilise mimari bölümleri için kullanılan isimlerdendir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "A",
            "options": json.dumps(["A) Transept", "B) Uçan Payanda", "C) Forum", "D) Gül Pencere", "E) Kaburgalı Tonoz", "F) Hiçbiri"]),
            "explanation": "• A) Transept: Erken Hristiyanlık döneminde Latin haçı planlı bazilikalarda kullanılan, ana nefi dik kesen enine koldur. Doğru cevaptır.\n• Diğerleri: B) Uçan Payanda, D) Gül Pencere ve E) Kaburgalı Tonoz Gotik mimari; C) Forum ise Antik Roma kamusal alanıdır.",
            "topic": "Erken Hristiyanlık",
            "difficulty": 2
        },
        {
            "text": "4) Evangelist sembolleri aşağıdakilerden hangisi veya hangilerinde doğru verilmiştir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "F",
            "options": json.dumps(["A) Boğa (Matta)", "B) Kartal (Matta)", "C) Aslan (Luka)", "D) Melek (Yuhanna)", "E) Boğa (Markos)", "F) Hiçbiri"]),
            "explanation": "• Dört İncil yazarının (Evangelist) geleneksel sembolleri şöyledir:\n• Matta → Melek (veya İnsan)\n• Markos → Aslan\n• Luka → Boğa (veya Öküz)\n• Yuhanna → Kartal\nSeçenekler arasında doğru eşleştirme bulunmadığı için doğru cevap 'Hiçbiri'dir.",
            "topic": "Erken Hristiyanlık",
            "difficulty": 4
        },
        {
            "text": "5) Aşağıdaki isimlerden hangisi veya hangileri Gotik dönem resim sanatçıları arasındadır?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "A",
            "options": json.dumps(["A) Simone Martini", "B) Leonardo Da Vinci", "C) Brunelleschi", "D) Michelangelo", "E) Alberti", "F) Hiçbiri"]),
            "explanation": "• Simone Martini: 14. yüzyıl İtalyan (Siena Okulu) ressamıdır ve Uluslararası Gotik üslubun önemli temsilcisidir. Doğru cevaptır.\n• Diğerleri: B) Leonardo da Vinci ve D) Michelangelo Yüksek Rönesans; C) Brunelleschi ve E) Alberti ise Erken Rönesans dönemi sanatçılarıdır (daha çok mimar olarak bilinirler).",
            "topic": "Gotik Resim",
            "difficulty": 2
        },
        {
            "text": "6) Yerebatan Sarnıcı, Binbirdirek Sarnıcı gibi profan yapıların inşa edildiği dönem aşağıdakilerden hangisi veya hangileridir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "F",
            "options": json.dumps(["A) Romanesk", "B) Gotik", "C) Karolenj", "D) Ottonyen", "E) Merovenj", "F) Hiçbiri"]),
            "explanation": "• İstanbul'daki Yerebatan Sarnıcı (6. yy) ve Binbirdirek Sarnıcı (4-6. yy) gibi büyük sivil (profan) su yapıları Bizans İmparatorluğu döneminde inşa edilmiştir.\n• Seçenekler Orta Çağ Avrupa'sının farklı dönemlerini temsil eder, ancak hiçbiri Bizans değildir. Bu nedenle Doğru cevap 'Hiçbiri'dir.",
            "topic": "Bizans Mimarisi",
            "difficulty": 4
        },
        {
            "text": "7) Genellikle kırmızı, mavi ve sarı renklerin kullanıldığı ve dönemi itibariyle duvar resimlerini dahi gölgede bırakan vitray süslemeleri aşağıdaki hangi dönem veya dönemlerde görülmektedir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "D",
            "options": json.dumps(["A) Merovenj", "B) Ottonyen", "C) Karolenj", "D) Gotik", "E) Romanesk", "F) Hiçbiri"]),
            "explanation": "• Gotik: Gotik mimaride, özellikle katedrallerde, duvar yüzeyleri incelmiş ve yerini büyük, renkli camlarla (vitray) süslenmiş pencerelere bırakmıştır. Bu vitraylar, İncil'den sahneleri anlatır, iç mekanı renkli bir ışıkla doldurur ve duvar resimlerinin (fresklerin) önemini ikinci plana itmiştir. Kırmızı, mavi ve sarı gibi canlı renkler bu dönem vitraylarında sıkça kullanılmıştır.\n• Diğerleri: Diğer dönemlerde vitray kullanımı olsa da, Gotik dönemdeki kadar baskın ve gelişmiş değildi.",
            "topic": "Gotik Sanatı",
            "difficulty": 2
        },
        {
            "text": "8) Aşağıdaki seçenek veya seçeneklerden hangisi Bizans dini mimari yapılarının plan özelliklerine göre verilen isimlerindendir?",
            "image_path": None,
            "answer_type": "double_choice",
            "correct_answer": "C,D",
            "options": json.dumps(["A) Manastır", "B) Narteks", "C) Kubbeli Bazilika", "D) Rotunda", "E) Obelisk", "F) Hiçbiri"]),
            "explanation": "• Kubbeli Bazilika: Bazilika planının merkezi kubbe ile birleştiği, Ayasofya gibi yapılarda görülen Bizans'a özgü önemli bir plan tipidir. Doğrudur.\n• Rotunda: Merkezi (yuvarlak/çokgen) planlı yapılar için genel bir terimdir ve Bizans'ta da San Vitale gibi örnekleri bulunur. Doğrudur.\n• Diğerleri: A) Manastır bir yapılar kompleksidir. B) Narteks kilisenin bir bölümüdür. E) Obelisk bir anıttır.",
            "topic": "Bizans Mimarisi",
            "difficulty": 3
        },
        {
            "text": "9) Romanesk dönemde inşa edilen yapılardan hangisi veya hangileri aşağıdaki seçeneklerde doğru olarak yazılmıştır?",
            "image_path": None,
            "answer_type": "double_choice",
            "correct_answer": "A,E",
            "options": json.dumps(["A) St. Etienne Kilisesi", "B) St. Vitale Kilisesi", "C) St. Michael Kilisesi", "D) St. Riquier Kilisesi", "E) Pisa", "F) Hiçbiri"]),
            "explanation": "• St. Etienne Kilisesi (Caen, Fransa): Romanesk mimarinin önemli ve karakteristik örneklerinden biridir. Doğrudur.\n• Pisa: Pisa Katedrali kompleksi (Katedral, Kule, Vaftizhane) İtalyan Romanesk mimarisinin en bilinen örneklerindendir. Doğrudur.\n• Diğerleri: B) St. Vitale (Bizans), C) St. Michael (Hildesheim) (Ottonyen/Erken Romanesk), D) St. Riquier (Karolenj).",
            "topic": "Romanesk Mimarisi",
            "difficulty": 3
        },
        {
            "text": "10) Aşağıdaki seçenek veya seçeneklerden hangisindeki dönemde görülen Tympanum rölyeflerinde figürler orantısız, uzun ve hareketleri mekanik şekilde betimlenmiştir?",
            "image_path": None,
            "answer_type": "single_choice",
            "correct_answer": "F",
            "options": json.dumps(["A) Karolenj", "B) Bizans", "C) Merovenj", "D) Rönesans", "E) Ottonyen", "F) Hiçbiri"]),
            "explanation": "• Soruda tarif edilen üslup Romanesk dönemine aittir. Seçeneklerde Romanesk olmadığı için Doğru cevap 'Hiçbiri'dir.",
            "topic": "Romanesk Heykel",
            "difficulty": 4
        }
    ]

    for q in questions_to_insert:
        # Sorunun veritabanında olup olmadığını kontrol et
        cursor.execute("SELECT id FROM questions WHERE text = ?", (q["text"],))
        if cursor.fetchone() is None:
            # Soru yoksa ekle
            cursor.execute(
                "INSERT INTO questions (text, image_path, answer_type, correct_answer, options, explanation, topic, difficulty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (q["text"], q["image_path"], q["answer_type"], q["correct_answer"], q["options"], q["explanation"], q["topic"], q["difficulty"])
            )
            logger.info(f"Soru eklendi: {q['text'][:50]}...")
        else:
            # Soru zaten varsa güncelleme (isteğe bağlı, şimdilik atlanıyor)
            logger.info(f"Soru zaten mevcut, atlanıyor: {q['text'][:50]}...")

    conn.commit()
    conn.close()
    logger.info("Örnek sorular veritabanına eklendi/kontrol edildi.")

if __name__ == '__main__':
    setup_database()
    insert_sample_questions()
    print("Veritabanı kurulumu ve örnek veri ekleme tamamlandı.")
    print("Artık ana bot dosyasını (main.py) çalıştırabilirsiniz.")

