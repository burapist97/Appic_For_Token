import sys
import subprocess
import os

# ==========================================
#   OTOMATİK KÜTÜPHANE YÜKLEYİCİ
# ==========================================
def bagimliliklari_kontrol_et_ve_yukle():
    gerekli_kutuphaneler = {
        "customtkinter": "customtkinter",
        "pynput": "pynput",
        "PIL": "pillow"
    }
    eksikler = []
    for modul_adi, pip_adi in gerekli_kutuphaneler.items():
        try:
            __import__(modul_adi)
        except ImportError:
            eksikler.append(pip_adi)
            
    if eksikler:
        print(f"\n[SİSTEM] Eksik kütüphaneler tespit edildi, otomatik yükleniyor: {eksikler}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *eksikler])
        print("[SİSTEM] Tüm kütüphaneler başarıyla yüklendi!\n")

bagimliliklari_kontrol_et_ve_yukle()

# ==========================================
#         GEREKLİ KÜTÜPHANELER
# ==========================================
import customtkinter as ctk
import threading
import time
import sqlite3
import json
import re
import math
import io
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
from pynput.keyboard import Listener, Key
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TestOtomasyonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Appium Görsel Inspector & Kayıt Motoru")
        self.geometry("1050x700")
        
        if getattr(sys, 'frozen', False):
            self.ana_dizin = os.path.dirname(sys.executable)
        else:
            self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
            
        self.db_yolu = os.path.join(self.ana_dizin, "test_merkezi.db")
        self.adb_yolu = "adb" 
        
        self.hata_klasoru = os.path.join(self.ana_dizin, "hata_gorselleri")
        os.makedirs(self.hata_klasoru, exist_ok=True) 

        self.kayit_aktif = False
        self.gecici_dokunuslar = []
        self.klavye_dinleyici = None
        self.adim_sayaci = 1
        
        self.ui_w = 360
        self.ui_h = 640
        
        self.aktif_ekran_xml = ""
        self.ekran_genislik = 1080
        self.ekran_yukseklik = 1920

        self.cihaz_cozunurlugunu_al()
        self.veritabanini_hazirla()

        # --- ARAYÜZ KURULUMU ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="INSPECTOR", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=10)

        self.btn_kayit_ekran = ctk.CTkButton(self.sidebar_frame, text="Yeni Görsel Kayıt", command=self.goster_kayit)
        self.btn_kayit_ekran.pack(pady=10, padx=20)

        self.btn_liste_ekran = ctk.CTkButton(self.sidebar_frame, text="Testleri Yönet & Çıkar", command=self.goster_liste)
        self.btn_liste_ekran.pack(pady=10, padx=20)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.baslangic_ekrani()

    def cihaz_cozunurlugunu_al(self):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            sonuc = subprocess.run([self.adb_yolu, "shell", "wm", "size"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r"size:\s*(\d+)x(\d+)", sonuc.stdout)
            if match:
                self.ekran_genislik = int(match.group(1))
                self.ekran_yukseklik = int(match.group(2))
        except Exception: pass

    def veritabanini_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS case_bazli_testler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, yetkili TEXT, uygulama TEXT, amac TEXT,
            case_adi TEXT, aksiyonlar TEXT, beklenen_xml TEXT, telefon_modeli TEXT, notlar TEXT)""")
        conn.commit()
        conn.close()

    def temizle(self):
        self.kayit_aktif = False
        for widget in self.main_frame.winfo_children(): widget.destroy()

    def baslangic_ekrani(self):
        self.temizle()
        lbl = ctk.CTkLabel(self.main_frame, text="XPath Tabanlı Appium Inspector'a Hoş Geldiniz!\n'Yeni Görsel Kayıt' ile başlayın.", font=("Arial", 16))
        lbl.pack(expand=True)

    # ==========================================
    #   1. CANLI INSPECTOR VE KAYIT
    # ==========================================
    def goster_kayit(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📱 Canlı Appium Inspector", font=("Arial", 18, "bold")).pack(pady=5)
        
        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=10, pady=5)
        
        self.entry_ad = ctk.CTkEntry(form_frame, placeholder_text="Senaryo Adı (Örn: Login)", width=200)
        self.entry_ad.grid(row=0, column=0, padx=5, pady=2)
        
        self.buton_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buton_frame.pack(pady=5)
        
        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="▶️ INSPECTOR'I BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
        self.btn_baslat.grid(row=0, column=0, padx=5)
        self.btn_bitir = ctk.CTkButton(self.buton_frame, text="🛑 Kaydı Bitir (ESC)", fg_color="red", state="disabled", command=self.kaydi_bitir_islem)
        self.btn_bitir.grid(row=0, column=1, padx=5)

        content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.screen_frame = ctk.CTkFrame(content_frame, width=self.ui_w+20, fg_color="#1e1e1e")
        self.screen_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        self.lbl_ekran = ctk.CTkLabel(self.screen_frame, text="Bağlantı Kuruluyor...", width=self.ui_w, height=self.ui_h, fg_color="#000000")
        self.lbl_ekran.pack(pady=10, padx=10)
        
        self.lbl_ekran.bind("<Button-1>", self.sol_tik_basildi)
        self.lbl_ekran.bind("<ButtonRelease-1>", self.sol_tik_birakildi)
        self.lbl_ekran.bind("<Button-2>", self.sag_tik_menusu)
        self.lbl_ekran.bind("<Button-3>", self.sag_tik_menusu)
        
        self.log_kutusu = ctk.CTkTextbox(content_frame, height=560)
        self.log_kutusu.pack(side="right", fill="both", expand=True, pady=10, padx=10)
        self.log_kutusu.insert("0.0", "Inspector Hazır. Tıklamalarınız sadece XPath olarak kaydedilecektir.\n")

    def ekran_yayini_dongusu(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        temp_gorsel_yolu = os.path.join(self.hata_klasoru, "temp_canli_ekran.png")
        
        while self.kayit_aktif:
            try:
                subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_canli.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_canli.png", temp_gorsel_yolu], capture_output=True, creationflags=c_flags)
                
                if os.path.exists(temp_gorsel_yolu):
                    img = Image.open(temp_gorsel_yolu)
                    img_resized = img.resize((self.ui_w, self.ui_h))
                    ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(self.ui_w, self.ui_h))
                    self.after(0, lambda resim=ctk_img: self.lbl_ekran.configure(image=resim, text=""))
            except Exception: pass
            time.sleep(0.3)

    # DİKKAT: Cihazı kitlememesi için sadece tıklama anında 1 kereliğine çalışır.
    def guncel_xml_tek_seferlik_cek(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            subprocess.run([self.adb_yolu, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], capture_output=True, creationflags=c_flags)
            xml_data = subprocess.check_output([self.adb_yolu, "shell", "cat", "/sdcard/window_dump.xml"], creationflags=c_flags).decode('utf-8', errors='ignore')
            self.aktif_ekran_xml = xml_data
        except Exception: pass

    # SADECE XPATH ÜRETEN FONKSİYON (Koordinat Dönmez)
    def xpath_hedef_bul(self, gercek_x, gercek_y):
        self.guncel_xml_tek_seferlik_cek() # XML'i O AN çek
        if not self.aktif_ekran_xml: return "//android.view.View"
        
        try:
            root = ET.fromstring(self.aktif_ekran_xml)
            en_kucuk_alan = float('inf')
            nihai_hedef = None
            TOLERANS = 30

            for elem in root.iter():
                bounds = elem.attrib.get('bounds')
                if bounds:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        if (x1 - TOLERANS) <= gercek_x <= (x2 + TOLERANS) and (y1 - TOLERANS) <= gercek_y <= (y2 + TOLERANS):
                            alan = (x2 - x1) * (y2 - y1)
                            if 0 < alan < en_kucuk_alan:
                                en_kucuk_alan = alan
                                nihai_hedef = elem.attrib
            
            if nihai_hedef:
                # Appium Inspector XPath Öncelik Mantığı
                if nihai_hedef.get('resource-id'): return f"//*[@resource-id='{nihai_hedef.get('resource-id')}']"
                elif nihai_hedef.get('text'): return f"//*[@text='{nihai_hedef.get('text')}']"
                elif nihai_hedef.get('content-desc'): return f"//*[@content-desc='{nihai_hedef.get('content-desc')}']"
                else: 
                    cls = nihai_hedef.get('class', 'android.view.View')
                    bnd = nihai_hedef.get('bounds')
                    return f"//{cls}[@bounds='{bnd}']"
                    
        except Exception: pass
        return "//android.view.View"

    def sol_tik_basildi(self, event):
        if not self.kayit_aktif: return
        self.bas_x = event.x
        self.bas_y = event.y

    def sol_tik_birakildi(self, event):
        if not self.kayit_aktif: return
        bitis_x = event.x
        bitis_y = event.y
        mesafe = math.hypot(bitis_x - getattr(self, 'bas_x', 0), bitis_y - getattr(self, 'bas_y', 0))
        
        gercek_x = int((bitis_x / self.ui_w) * self.ekran_genislik)
        gercek_y = int((bitis_y / self.ui_h) * self.ekran_yukseklik)

        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        if mesafe < 30: # TIKLAMA
            self.after(0, lambda: self.log_yaz("🔍 Obje taranıyor..."))
            
            def islem_yap():
                xpath = self.xpath_hedef_bul(gercek_x, gercek_y)
                # Sadece XPath'i kaydediyoruz (T: Tıkla, M: Metin)
                self.gecici_dokunuslar.append(f"T;;;{xpath}") 
                self.after(0, lambda: self.log_yaz(f"🎯 XPath Bulundu: {xpath}"))
                
                # Gerçek cihaza dokunuş gönder (Sonraki sayfaya geçmesi için)
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                
            threading.Thread(target=islem_yap).start()
            
        else: # KAYDIRMA (Sürükleme)
            fark_x = bitis_x - getattr(self, 'bas_x', 0)
            fark_y = bitis_y - getattr(self, 'bas_y', 0)
            yon = "down" if fark_y > 0 else "up"
            if abs(fark_x) > abs(fark_y): yon = "right" if fark_x > 0 else "left"
            
            self.gecici_dokunuslar.append(f"S;;;{yon}")
            self.after(0, lambda: self.log_yaz(f"👆 Kaydırma Eklendi: {yon}"))
            
            gercek_bas_x = int((getattr(self, 'bas_x', 0) / self.ui_w) * self.ekran_genislik)
            gercek_bas_y = int((getattr(self, 'bas_y', 0) / self.ui_h) * self.ekran_yukseklik)
            threading.Thread(target=lambda: subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(gercek_bas_x), str(gercek_bas_y), str(gercek_x), str(gercek_y), "400"], creationflags=c_flags)).start()

    def sag_tik_menusu(self, event):
        if not self.kayit_aktif: return
        gercek_x = int((event.x / self.ui_w) * self.ekran_genislik)
        gercek_y = int((event.y / self.ui_h) * self.ekran_yukseklik)
        
        self.after(0, lambda: self.log_yaz("🔍 Metin kutusu taranıyor..."))
        
        def menuyu_hazirla():
            xpath = self.xpath_hedef_bul(gercek_x, gercek_y)
            self.after(0, lambda: self._popup_ac(gercek_x, gercek_y, xpath))
            
        threading.Thread(target=menuyu_hazirla).start()

    def _popup_ac(self, gercek_x, gercek_y, xpath):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        popup = ctk.CTkToplevel(self)
        popup.title("Kutu İşlemleri")
        popup.geometry("300x200")
        popup.attributes("-topmost", True)
        
        veri_girisi = ctk.CTkEntry(popup, placeholder_text="Yazılacak metin...", width=200)
        veri_girisi.pack(pady=20)
        
        def yaz():
            val = veri_girisi.get()
            if not val: return
            self.gecici_dokunuslar.append(f"M;;;{xpath};;;{val}")
            self.log_yaz(f"✍️ XPath'e Metin Eklendi: '{val}'")
            popup.destroy()
            
            def cihaza_yaz():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
            threading.Thread(target=cihaza_yaz).start()
            
        ctk.CTkButton(popup, text="✍️ Metin Yaz", fg_color="green", command=yaz).pack(pady=5)

    def kaydi_tetikle(self):
        self.guncel_test_adi = self.entry_ad.get()
        if not self.guncel_test_adi:
            self.log_yaz("\n❌ Lütfen bir Senaryo Adı girin!")
            return

        self.cihaz_cozunurlugunu_al()
        self.btn_baslat.configure(state="disabled")
        self.btn_bitir.configure(state="normal")
        
        self.kayit_aktif = True
        self.gecici_dokunuslar = []
        
        self.log_yaz(f"\n🚀 '{self.guncel_test_adi}' Inspector devrede!\nEkrana tıklayarak adımları kaydedebilirsiniz.")
        threading.Thread(target=self.ekran_yayini_dongusu, daemon=True).start()
        
        if self.klavye_dinleyici: self.klavye_dinleyici.stop()
        self.klavye_dinleyici = Listener(on_press=self.klavye_dinle)
        self.klavye_dinleyici.start()

    def klavye_dinle(self, key):
        if not self.kayit_aktif: return 
        if key == Key.esc: self.after(0, self.kaydi_bitir_islem)

    def kaydi_bitir_islem(self):
        self.kayit_aktif = False
        if self.klavye_dinleyici:
            self.klavye_dinleyici.stop()
            self.klavye_dinleyici = None
            
        if self.gecici_dokunuslar:
            kopya = list(self.gecici_dokunuslar)
            aksiyon_str = "|".join(kopya)
            
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO case_bazli_testler (ana_test_adi, aksiyonlar) VALUES (?,?)", (self.guncel_test_adi, aksiyon_str))
            conn.commit()
            conn.close()
            
        try:
            self.btn_baslat.configure(state="normal")
            self.btn_bitir.configure(state="disabled")
            self.log_yaz("\n🎉 KAYIT TAMAMLANDI! Artık dışa aktarabilirsiniz.\n")
        except Exception: pass

    def log_yaz(self, mesaj):
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")

    # ==========================================
    #   2. XPATH TABANLI EXPORT (DIŞA AKTARIM)
    # ==========================================
    def goster_liste(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="🚀 Kayıtlı Testleri IDE'ye Çıkar", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)
        self.arama_entry = ctk.CTkEntry(ust_frame, placeholder_text="Ara...", width=400)
        self.arama_entry.pack(side="left", padx=10)
        self.arama_entry.bind("<KeyRelease>", self.listeyi_guncelle)

        self.test_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=400)
        self.test_listesi.pack(pady=10, padx=10, fill="both", expand=True)
        self.listeyi_guncelle()

    def listeyi_guncelle(self, event=None):
        for widget in self.test_listesi.winfo_children(): widget.destroy()
        if not os.path.exists(self.db_yolu): return
        arama = self.arama_entry.get().strip()
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ana_test_adi FROM case_bazli_testler WHERE ana_test_adi LIKE ?", (f'%{arama}%',))
            kayitlar = cursor.fetchall()
            conn.close()

            for (test_adi,) in kayitlar:
                satir = ctk.CTkFrame(self.test_listesi, fg_color="#2b2b2b")
                satir.pack(fill="x", pady=5, padx=5)
                ctk.CTkLabel(satir, text=f"📂 {test_adi}", font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                ctk.CTkButton(satir, text="📤 Sadece XPATH Scripti Üret", width=180, fg_color="#2980b9", command=lambda t=test_adi: self.testi_disa_aktar(t)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    # SIFIR KOORDİNAT - %100 XPATH TEMPLATE EXPORT
    def testi_disa_aktar(self, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar FROM case_bazli_testler WHERE ana_test_adi = ?", (test_adi,))
            satirlar = cursor.fetchall()
            conn.close()
            if not satirlar: return
            
            gen_code = "import time\nfrom appium import webdriver\nfrom appium.options.android import UiAutomator2Options\nfrom appium.webdriver.common.appiumby import AppiumBy\nfrom selenium.webdriver.support.ui import WebDriverWait\nfrom selenium.webdriver.support import expected_conditions as EC\n\n"
            
            gen_code += "def obje_bul(driver, xpath, timeout=10):\n    wait = WebDriverWait(driver, timeout)\n    return wait.until(EC.presence_of_element_located((AppiumBy.XPATH, xpath)))\n\n"
            
            gen_code += f"options = UiAutomator2Options()\noptions.no_reset = True\n"
            gen_code += "driver = webdriver.Remote('http://127.0.0.1:4723', options=options)\n\n"

            gen_code += f"def {test_adi.replace(' ', '_')}():\n"
            
            for s in satirlar:
                dokunuslar = [n for n in s[0].split("|") if n]
                for nokta in dokunuslar:
                    parts = nokta.split(";;;")
                    islem = parts[0]
                    
                    if islem == "T":
                        xpath = parts[1]
                        gen_code += f"    # Tıklama Adımı\n"
                        gen_code += f"    obje_bul(driver, r'''{xpath}''').click()\n    time.sleep(1)\n\n"
                    elif islem == "M":
                        xpath = parts[1]
                        val = parts[2]
                        gen_code += f"    # Metin Yazma Adımı\n"
                        gen_code += f"    kutu = obje_bul(driver, r'''{xpath}''')\n"
                        gen_code += f"    kutu.click()\n    kutu.clear()\n    kutu.send_keys('{val}')\n    time.sleep(1)\n\n"
                    elif islem == "S":
                        yon = parts[1]
                        gen_code += f"    # Kaydırma İşlemi (Swipe {yon})\n"
                        gen_code += f"    driver.execute_script('mobile: scroll', {{'direction': '{yon}'}})\n    time.sleep(1)\n\n"

            gen_code += "try:\n" + f"    {test_adi.replace(' ', '_')}()\n" + "finally:\n    driver.quit()\n"

            dosya_yolu = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"{test_adi.replace(' ', '_')}_Appium_Script.py", title="Appium Scripti Kaydet")
            if dosya_yolu:
                with open(dosya_yolu, "w", encoding="utf-8") as f: f.write(gen_code)
                messagebox.showinfo("Başarılı", f"Sıfır koordinatlı saf XPath Appium scripti üretildi!\nDosya: {dosya_yolu}")
        except Exception as e: messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

if __name__ == "__main__":
    app = TestOtomasyonApp()
    app.mainloop()