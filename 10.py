import customtkinter as ctk
import tkinter as tk
import time
import math
import threading
from PIL import Image, ImageTk

class CanliEtkilesimMotoru(ctk.CTkFrame):
    def __init__(self, master, adb_yolu, donanim_genislik, donanim_yukseklik):
        super().__init__(master)
        
        self.adb_yolu = adb_yolu
        self.ekran_w = donanim_genislik
        self.ekran_h = donanim_yukseklik
        
        # Streamlit paneli için üretilecek adımların tutulduğu liste
        self.kaydedilen_adimlar = [] 
        
        # Etkileşim değişkenleri
        self.baslangic_x = 0
        self.baslangic_y = 0
        self.baslangic_zamani = 0
        
        self.arayuzu_olustur()
        self.olay_dinleyicileri_bagla()
        
        # Scrcpy veya ADB üzerinden canlı akışı başlat
        self.canli_akis_aktif = True
        threading.Thread(target=self.sahte_canli_akis_baslat, daemon=True).start()

    def arayuzu_olustur(self):
        # Sol Taraf: Canlı Ekran Yansıtması
        self.lbl_ekran = ctk.CTkLabel(self, text="Ekran Yükleniyor...", width=360, height=640, fg_color="#2b2b2b")
        self.lbl_ekran.pack(side="left", padx=20, pady=20)
        
        # Sağ Taraf: Canlı Kaydedilen Adımlar (Streamlit Önizlemesi)
        self.log_frame = ctk.CTkScrollableFrame(self, width=400, height=640)
        self.log_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(self.log_frame, text="📝 Kaydedilen Adımlar", font=("Arial", 16, "bold")).pack(pady=10)

    def olay_dinleyicileri_bagla(self):
        # Sol Tık (Basma ve Bırakma - Tap & Swipe için)
        self.lbl_ekran.bind("<Button-1>", self.sol_tik_basildi)
        self.lbl_ekran.bind("<ButtonRelease-1>", self.sol_tik_birakildi)
        
        # Sağ Tık (macOS/Windows uyumluluğu için Button-2 ve Button-3)
        self.lbl_ekran.bind("<Button-2>", self.sag_tik_kutu_menusu)
        self.lbl_ekran.bind("<Button-3>", self.sag_tik_kutu_menusu)

    # ==========================================
    # 1. SOL TIK OLAYLARI (TAP & SWIPE)
    # ==========================================
    def sol_tik_basildi(self, event):
        self.baslangic_x = event.x
        self.baslangic_y = event.y
        self.baslangic_zamani = time.time()

    def sol_tik_birakildi(self, event):
        bitis_x = event.x
        bitis_y = event.y
        gecen_sure = time.time() - self.baslangic_zamani
        
        # Mesafe hesaplama (Piksel cinsinden)
        mesafe = math.hypot(bitis_x - self.baslangic_x, bitis_y - self.baslangic_y)
        
        # Arka planda XML'den XPath bulma (Mevcut akilli_hedef_bul fonksiyonunuzu çağırır)
        hedef_xpath = f"//android.widget.Button[@bounds='[{bitis_x},{bitis_y}]...']" # Örnek
        
        if mesafe < 15: # 15 pikselden az hareket ettiyse bu bir TIKLAMADIR
            self.adim_ekle(action="Tıkla", xpath=hedef_xpath, x=bitis_x, y=bitis_y)
            # ADB ile cihaza gerçek tıklamayı gönder
            # subprocess.run([self.adb_yolu, "shell", "input", "tap", gercek_x, gercek_y])
        else: # Mesafe büyükse bu bir KAYDIRMADIR (Swipe)
            fark_x = bitis_x - self.baslangic_x
            fark_y = bitis_y - self.baslangic_y
            
            if abs(fark_y) > abs(fark_x):
                yon = "Aşağı" if fark_y > 0 else "Yukarı"
            else:
                yon = "Sağa" if fark_x > 0 else "Sola"
                
            self.adim_ekle(action="Kaydır (Swipe)", direction=yon, x=self.baslangic_x, y=self.baslangic_y)

    # ==========================================
    # 2. SAĞ TIK OLAYI (METİN YAZ / SİL MENÜSÜ)
    # ==========================================
    def sag_tik_kutu_menusu(self, event):
        # Tıklanan yerin XPath'ini bul
        hedef_xpath = f"//android.widget.EditText[@bounds='[{event.x},{event.y}]...']" # Örnek
        
        # Popup Menü Oluştur
        popup = ctk.CTkToplevel(self)
        popup.title("Kutu İşlemleri")
        popup.geometry("350x250")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Bu alanda ne yapmak istiyorsunuz?", font=("Arial", 14, "bold")).pack(pady=10)
        
        metin_girdisi = ctk.CTkEntry(popup, placeholder_text="Yazılacak metni girin...", width=250)
        metin_girdisi.pack(pady=10)
        
        def metin_yaz():
            girilen_deger = metin_girdisi.get()
            if girilen_deger:
                self.adim_ekle(action="Metin Yaz", xpath=hedef_xpath, val=girilen_deger)
                popup.destroy()
                
        def icerigi_sil():
            self.adim_ekle(action="Sistem Tuşu", sys_key="Kutuyu Temizle", xpath=hedef_xpath)
            popup.destroy()

        ctk.CTkButton(popup, text="✍️ Metin Yaz", fg_color="green", command=metin_yaz).pack(pady=5)
        ctk.CTkButton(popup, text="🧹 İçeriği Sil", fg_color="red", command=icerigi_sil).pack(pady=5)

    # ==========================================
    # 3. STREAMLIT İÇİN JSON FORMATINDA ADIM ÜRETİMİ
    # ==========================================
    def adim_ekle(self, action, xpath="", val="", direction="Aşağı", sys_key="", x=0, y=0):
        # Tam olarak appium_panel.py'nin beklediği yapı
        yeni_adim = {
            "step_name": f"{action} Adımı",
            "action": action,
            "xpath": xpath,
            "val": val,
            "count": 1,
            "direction": direction,
            "x": x,
            "y": y,
            "sys_key": sys_key,
            "exact_match": False
        }
        
        self.kaydedilen_adimlar.append(yeni_adim)
        
        # Arayüzde log olarak göster
        satir = ctk.CTkLabel(self.log_frame, text=f"✅ {action} eklendi. (Değer: {val if val else yon if action=='Kaydır (Swipe)' else x})", anchor="w")
        satir.pack(fill="x", pady=2)
        
        # Burada üretilen self.kaydedilen_adimlar listesini test bitiminde doğrudan JSON'a çevirip
        # .py dosyanızın # --- IDE_METADATA_START --- bloğuna yazdırabilirsiniz.

    # ==========================================
    # 4. CANLI EKRAN AKIŞI (SCRCPY / ADB)
    # ==========================================
    def sahte_canli_akis_baslat(self):
        """ 
        Gerçek uygulamada burada scrcpy-client kütüphanesi veya hızlı ADB screencap döngüsü olur.
        OpenCV ile alınan frame, CTkImage'a dönüştürülüp self.lbl_ekran.configure(image=...) ile basılır.
        """
        while self.canli_akis_aktif:
            # frame = get_frame_from_scrcpy()
            # ctk_img = ctk.CTkImage(light_image=Image.fromarray(frame), size=(360, 640))
            # self.lbl_ekran.configure(image=ctk_img)
            time.sleep(0.03) # ~30 FPS