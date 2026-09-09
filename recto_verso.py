import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font
import subprocess
import os
import json
import platform
import threading
from datetime import datetime
from PIL import Image, ImageTk, ImageChops, ImageFilter, ImageEnhance, ImageDraw, ImageFont

# --- Fichier de configuration ---
CONFIG_FILE = os.path.expanduser("~/.scanner_id_config.json")

# --- Thème unique "clair_moderne" ---
THEME = {
    "bg": "#F3F4F6",
    "btn": "#E5E7EB",
    "btn_hover": "#D1D5DB",
    "text": "#1F2937",
    "menu_bg": "#FFFFFF",
    "white": "#FFFFFF"
}

# --- Classe Layer ---
class Layer:
    def __init__(self, name, image=None, x=0, y=0, opacity=1.0, visible=True, rotation=0, layer_type="custom"):
        self.name = name
        self.image = image
        self.x = x
        self.y = y
        self.opacity = opacity
        self.visible = visible
        self.rotation = rotation
        self.type = layer_type

    def copy(self):
        return Layer(self.name, self.image.copy() if self.image else None,
                     self.x, self.y, self.opacity, self.visible, self.rotation, self.type)

# --- Application principale ---
class ScannerIDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scanner d'Identité - Éditeur interactif PDF & Impression")
        self.root.geometry("1300x900")
        
        self.appliquer_couleurs_theme()

        self.recto_path = "/tmp/id_recto.png"
        self.verso_path = "/tmp/id_verso.png"
        self.temp_print_pdf = "/tmp/id_print_temp.pdf"
        
        self.scanners_list = {}
        self.sources_choix = ["Vitre (Flatbed)", "Auto (Par défaut)", "Chargeur auto (ADF)"]
        
        # --- Calques ---
        self.layers = []
        self.selected_layer_index = -1
        self.next_layer_id = 0

        # --- Variables du filigrane (pour le panneau de création) ---
        self.watermark_text = "Filigrane"
        self.watermark_font_family = "Arial"
        self.watermark_size = 72
        self.watermark_color = "#808080"
        self.watermark_angle = 0
        self.watermark_image_path = None

        # Dimensions de l'aperçu
        self.canvas_w = 500
        self.canvas_h = 707  # ratio A4
        self.scale_factor = self.canvas_w / 2480.0

        # Drag & drop
        self.drag_data = {"item": None, "x": 0, "y": 0, "layer_index": -1}

        self.charger_config()  # pour scanner et source sauvegardés
        self.setup_menu()
        self.setup_style()
        self.setup_ui()
        self.detecter_scanners()

    # --- Configuration (chargement/sauvegarde) ---
    def charger_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.saved_scanner = data.get("scanner", "")
                    self.saved_source = data.get("source", "Vitre (Flatbed)")
            except:
                self.saved_scanner = ""
                self.saved_source = "Vitre (Flatbed)"
        else:
            self.saved_scanner = ""
            self.saved_source = "Vitre (Flatbed)"

    def sauvegarder_config(self, afficher_message=False):
        data = {
            "scanner": self.combo_scanners.get() if hasattr(self, 'combo_scanners') else "",
            "source": self.combo_source.get() if hasattr(self, 'combo_source') else "Vitre (Flatbed)"
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f)
            if afficher_message:
                messagebox.showinfo("Configuration", "Configuration sauvegardée.")
        except Exception as e:
            if afficher_message:
                messagebox.showerror("Erreur", f"Impossible de sauvegarder : {e}")

    def appliquer_couleurs_theme(self):
        t = THEME
        self.BG_COLOR = t["bg"]
        self.BTN_COLOR = t["btn"]
        self.BTN_HOVER = t["btn_hover"]
        self.TEXT_COLOR = t["text"]
        self.MENU_BG = t["menu_bg"]
        self.WHITE = t["white"]
        if hasattr(self, 'root'):
            self.root.configure(bg=self.BG_COLOR)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Flat.TCombobox",
                        fieldbackground=self.WHITE,
                        background=self.BTN_COLOR,
                        foreground=self.TEXT_COLOR,
                        bordercolor=self.BG_COLOR,
                        lightcolor=self.BG_COLOR,
                        darkcolor=self.BG_COLOR,
                        arrowsize=14,
                        relief="flat")
        style.map("Flat.TCombobox",
                  background=[('readonly', self.BTN_COLOR)],
                  fieldbackground=[('readonly', self.WHITE)],
                  foreground=[('readonly', self.TEXT_COLOR)])

    def setup_menu(self):
        menubar = tk.Menu(self.root, bg=self.MENU_BG, fg=self.TEXT_COLOR, relief="flat", bd=0)
        menu_fichier = tk.Menu(menubar, bg=self.MENU_BG, fg=self.TEXT_COLOR, relief="flat", bd=0, activebackground=self.BTN_HOVER)
        menu_fichier.add_command(label="Exporter en PDF", command=self.export_pdf)
        menu_fichier.add_command(label="Imprimer le document", command=self.imprimer_document)
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Sauvegarder la configuration", command=lambda: self.sauvegarder_config(afficher_message=True))
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Quitter", command=self.root.quit)
        menubar.add_cascade(label="Fichier", menu=menu_fichier)
        
        menu_edition = tk.Menu(menubar, bg=self.MENU_BG, fg=self.TEXT_COLOR, relief="flat", bd=0, activebackground=self.BTN_HOVER)
        menu_edition.add_command(label="Rechercher les scanners", command=self.detecter_scanners)
        menu_edition.add_command(label="Effacer les scans", command=self.clear_scans)
        menubar.add_cascade(label="Édition", menu=menu_edition)
        
        menu_aide = tk.Menu(menubar, bg=self.MENU_BG, fg=self.TEXT_COLOR, relief="flat", bd=0, activebackground=self.BTN_HOVER)
        menu_aide.add_command(label="À propos", command=self.afficher_a_propos)
        menubar.add_cascade(label="Aide", menu=menu_aide)
        
        self.root.config(menu=menubar)

    def afficher_a_propos(self):
        fenetre_about = tk.Toplevel(self.root)
        fenetre_about.title("À propos")
        fenetre_about.geometry("400x340")
        fenetre_about.configure(bg=self.BG_COLOR)
        fenetre_about.resizable(False, False)
        fenetre_about.transient(self.root)
        fenetre_about.grab_set()

        tk.Label(fenetre_about, text="Scanner d'Identité", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=("Helvetica", 16, "bold")).pack(pady=(25, 5))
        tk.Label(fenetre_about, text="Outil pro de numérisation, recadrage,\nrotation et assemblage PDF interactif.", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=("Helvetica", 10)).pack(pady=5)
        tk.Label(fenetre_about, text="Version 1.025", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=("Helvetica", 11, "bold")).pack(pady=(10, 5))
        tk.Label(fenetre_about, text="Créé par Durand Joël\nContact : rd66lago@gmail.com", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=("Helvetica", 10)).pack(pady=5)
        tk.Label(fenetre_about, text="Licence : Logiciel libre de droit", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=("Helvetica", 10, "italic")).pack(pady=5)

        btn_fermer = tk.Button(fenetre_about, text="Fermer", font=("Helvetica", 10, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=25, pady=8, command=fenetre_about.destroy)
        btn_fermer.pack(side=tk.BOTTOM, pady=20)
        btn_fermer.bind("<Enter>", lambda e: btn_fermer.config(bg=self.BTN_HOVER))
        btn_fermer.bind("<Leave>", lambda e: btn_fermer.config(bg=self.BTN_COLOR))

    # --- Interface utilisateur : 3 zones horizontales ---
    def setup_ui(self):
        # Panneau principal avec 3 colonnes : gauche (haut et bas), droite (aperçu)
        main_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Colonne de gauche (scanner + calques)
        left_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # --- Partie haute : scanner ---
        top_frame = tk.Frame(left_frame, bg=self.MENU_BG, padx=15, pady=15)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(top_frame, text="Numérisation", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))

        # Ligne scanner
        row1 = tk.Frame(top_frame, bg=self.MENU_BG)
        row1.pack(fill=tk.X, pady=3)
        tk.Label(row1, text="Scanner :", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 10), width=10, anchor="w").pack(side=tk.LEFT)
        self.combo_scanners = ttk.Combobox(row1, style="Flat.TCombobox", state="readonly", font=("Helvetica", 10))
        self.combo_scanners.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn_refresh = tk.Button(row1, text="↻", font=("Helvetica", 12), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, width=3, command=self.detecter_scanners)
        btn_refresh.pack(side=tk.RIGHT)
        btn_refresh.bind("<Enter>", lambda e: btn_refresh.config(bg=self.BTN_HOVER))
        btn_refresh.bind("<Leave>", lambda e: btn_refresh.config(bg=self.BTN_COLOR))

        # Ligne source
        row2 = tk.Frame(top_frame, bg=self.MENU_BG)
        row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Source :", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 10), width=10, anchor="w").pack(side=tk.LEFT)
        self.combo_source = ttk.Combobox(row2, style="Flat.TCombobox", state="readonly", font=("Helvetica", 10))
        self.combo_source['values'] = self.sources_choix
        if self.saved_source in self.sources_choix:
            self.combo_source.set(self.saved_source)
        else:
            self.combo_source.current(0)
        self.combo_source.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Ligne réglages luminosité/contraste
        row3 = tk.Frame(top_frame, bg=self.MENU_BG)
        row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Lum./Cont.", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 10), width=10, anchor="w").pack(side=tk.LEFT)
        self.slider_lum = ttk.Scale(row3, from_=0.5, to=1.5, value=1.0, orient=tk.HORIZONTAL, command=lambda v: self.ajuster_images())
        self.slider_lum.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.slider_cont = ttk.Scale(row3, from_=0.5, to=1.5, value=1.0, orient=tk.HORIZONTAL, command=lambda v: self.ajuster_images())
        self.slider_cont.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Ligne boutons scan et rotation
        row4 = tk.Frame(top_frame, bg=self.MENU_BG)
        row4.pack(fill=tk.X, pady=5)
        btn_recto = tk.Button(row4, text="Scanner Recto", font=("Helvetica", 10, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=15, pady=5, command=self.scan_recto)
        btn_recto.pack(side=tk.LEFT, padx=2)
        btn_recto.bind("<Enter>", lambda e: btn_recto.config(bg=self.BTN_HOVER))
        btn_recto.bind("<Leave>", lambda e: btn_recto.config(bg=self.BTN_COLOR))
        btn_rot_recto = tk.Button(row4, text="↺ Recto", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=10, pady=5, command=lambda: self.pivoter_carte("recto"))
        btn_rot_recto.pack(side=tk.LEFT, padx=2)
        btn_rot_recto.bind("<Enter>", lambda e: btn_rot_recto.config(bg=self.BTN_HOVER))
        btn_rot_recto.bind("<Leave>", lambda e: btn_rot_recto.config(bg=self.BTN_COLOR))
        btn_verso = tk.Button(row4, text="Scanner Verso", font=("Helvetica", 10, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=15, pady=5, command=self.scan_verso)
        btn_verso.pack(side=tk.LEFT, padx=2)
        btn_verso.bind("<Enter>", lambda e: btn_verso.config(bg=self.BTN_HOVER))
        btn_verso.bind("<Leave>", lambda e: btn_verso.config(bg=self.BTN_COLOR))
        btn_rot_verso = tk.Button(row4, text="↺ Verso", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=10, pady=5, command=lambda: self.pivoter_carte("verso"))
        btn_rot_verso.pack(side=tk.LEFT, padx=2)
        btn_rot_verso.bind("<Enter>", lambda e: btn_rot_verso.config(bg=self.BTN_HOVER))
        btn_rot_verso.bind("<Leave>", lambda e: btn_rot_verso.config(bg=self.BTN_COLOR))

        # Vignettes
        row5 = tk.Frame(top_frame, bg=self.MENU_BG)
        row5.pack(fill=tk.X, pady=5)
        self.lbl_img_recto = tk.Label(row5, bg=self.MENU_BG, text="[ Recto ]", fg=self.TEXT_COLOR, font=("Helvetica", 9))
        self.lbl_img_recto.pack(side=tk.LEFT, padx=10)
        self.lbl_img_verso = tk.Label(row5, bg=self.MENU_BG, text="[ Verso ]", fg=self.TEXT_COLOR, font=("Helvetica", 9))
        self.lbl_img_verso.pack(side=tk.LEFT, padx=10)

        # --- Partie basse : calques et filigrane ---
        bottom_frame = tk.Frame(left_frame, bg=self.MENU_BG, padx=15, pady=15)
        bottom_frame.pack(fill=tk.BOTH, expand=True)

        # Séparer en deux colonnes : calques à gauche, filigrane à droite
        bottom_left = tk.Frame(bottom_frame, bg=self.MENU_BG)
        bottom_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        bottom_right = tk.Frame(bottom_frame, bg=self.MENU_BG)
        bottom_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Calques ---
        tk.Label(bottom_left, text="Calques", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))
        self.listbox_layers = tk.Listbox(bottom_left, height=6, bg=self.WHITE, fg=self.TEXT_COLOR, selectmode=tk.SINGLE, relief="flat", font=("Helvetica", 9))
        self.listbox_layers.pack(fill=tk.X, pady=5)
        self.listbox_layers.bind('<<ListboxSelect>>', self.on_layer_selected)

        # Contrôles des calques
        btn_frame = tk.Frame(bottom_left, bg=self.MENU_BG)
        btn_frame.pack(fill=tk.X, pady=2)
        btn_up = tk.Button(btn_frame, text="▲", font=("Helvetica", 10), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=5, command=self.move_layer_up)
        btn_up.pack(side=tk.LEFT, padx=2)
        btn_down = tk.Button(btn_frame, text="▼", font=("Helvetica", 10), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=5, command=self.move_layer_down)
        btn_down.pack(side=tk.LEFT, padx=2)
        btn_del = tk.Button(btn_frame, text="✕ Supprimer", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=8, command=self.delete_selected_layer)
        btn_del.pack(side=tk.LEFT, padx=2)
        btn_import = tk.Button(btn_frame, text="Importer image", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=8, command=self.import_image_layer)
        btn_import.pack(side=tk.LEFT, padx=2)

        tk.Label(bottom_left, text="Opacité", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 9)).pack(anchor="w", pady=(5,0))
        self.opacity_slider = ttk.Scale(bottom_left, from_=0.0, to=1.0, value=1.0, orient=tk.HORIZONTAL, command=self.on_opacity_change)
        self.opacity_slider.pack(fill=tk.X, pady=2)

        # --- Filigrane (création de nouveaux filigranes) ---
        tk.Label(bottom_right, text="Créer un filigrane", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))

        # Type
        wm_type_frame = tk.Frame(bottom_right, bg=self.MENU_BG)
        wm_type_frame.pack(fill=tk.X, pady=2)
        self.wm_type_var = tk.StringVar(value="texte")
        rb_texte = tk.Radiobutton(wm_type_frame, text="Texte", variable=self.wm_type_var, value="texte", bg=self.MENU_BG, fg=self.TEXT_COLOR, selectcolor=self.BG_COLOR, command=self.on_watermark_type_change)
        rb_texte.pack(side=tk.LEFT, padx=2)
        rb_image = tk.Radiobutton(wm_type_frame, text="Image", variable=self.wm_type_var, value="image", bg=self.MENU_BG, fg=self.TEXT_COLOR, selectcolor=self.BG_COLOR, command=self.on_watermark_type_change)
        rb_image.pack(side=tk.LEFT, padx=2)

        # Texte
        self.wm_text_frame = tk.Frame(bottom_right, bg=self.MENU_BG)
        self.wm_text_frame.pack(fill=tk.X, pady=2)
        tk.Label(self.wm_text_frame, text="Texte:", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.wm_text_entry = tk.Entry(self.wm_text_frame, bg=self.WHITE, fg=self.TEXT_COLOR, relief="flat", font=("Helvetica", 9))
        self.wm_text_entry.insert(0, "Filigrane")
        self.wm_text_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Police et taille
        font_frame = tk.Frame(bottom_right, bg=self.MENU_BG)
        font_frame.pack(fill=tk.X, pady=2)
        tk.Label(font_frame, text="Police:", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.font_list = sorted(font.families())
        self.combo_font = ttk.Combobox(font_frame, values=self.font_list, state="readonly", font=("Helvetica", 9), width=12)
        self.combo_font.set("Arial")
        self.combo_font.pack(side=tk.LEFT, padx=5)
        tk.Label(font_frame, text="Taille:", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 9)).pack(side=tk.LEFT, padx=(5,0))
        self.wm_size_spin = tk.Spinbox(font_frame, from_=10, to=300, width=5, bg=self.WHITE, fg=self.TEXT_COLOR, relief="flat", font=("Helvetica", 9))
        self.wm_size_spin.delete(0, tk.END)
        self.wm_size_spin.insert(0, "72")
        self.wm_size_spin.pack(side=tk.LEFT, padx=5)

        # Angle et couleur
        angle_color_frame = tk.Frame(bottom_right, bg=self.MENU_BG)
        angle_color_frame.pack(fill=tk.X, pady=2)
        tk.Label(angle_color_frame, text="Angle:", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.wm_angle_spin = tk.Spinbox(angle_color_frame, from_=-180, to=180, width=5, bg=self.WHITE, fg=self.TEXT_COLOR, relief="flat", font=("Helvetica", 9))
        self.wm_angle_spin.delete(0, tk.END)
        self.wm_angle_spin.insert(0, "0")
        self.wm_angle_spin.pack(side=tk.LEFT, padx=5)
        btn_color = tk.Button(angle_color_frame, text="Couleur", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=8, command=self.choose_watermark_color)
        btn_color.pack(side=tk.LEFT, padx=5)

        # Image
        self.wm_image_frame = tk.Frame(bottom_right, bg=self.MENU_BG)
        btn_load_wm_image = tk.Button(self.wm_image_frame, text="Charger image", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=8, command=self.load_watermark_image)
        btn_load_wm_image.pack(side=tk.LEFT, padx=2)
        btn_clear_wm_image = tk.Button(self.wm_image_frame, text="Effacer image", font=("Helvetica", 9), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=8, command=self.clear_watermark_image)
        btn_clear_wm_image.pack(side=tk.LEFT, padx=2)

        # Bouton pour ajouter un filigrane (crée un nouveau calque)
        btn_add_wm = tk.Button(bottom_right, text="Ajouter ce filigrane", font=("Helvetica", 10, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=15, pady=6, command=self.add_watermark_layer)
        btn_add_wm.pack(pady=10)
        btn_add_wm.bind("<Enter>", lambda e: btn_add_wm.config(bg=self.BTN_HOVER))
        btn_add_wm.bind("<Leave>", lambda e: btn_add_wm.config(bg=self.BTN_COLOR))

        # --- Panneau droit : aperçu ---
        right_frame = tk.Frame(main_frame, bg=self.MENU_BG, padx=15, pady=15)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right_frame, text="Aperçu (glisser/déposer)", bg=self.MENU_BG, fg=self.TEXT_COLOR, font=("Helvetica", 12, "bold")).pack(pady=(0, 10))

        self.canvas_pdf = tk.Canvas(right_frame, width=self.canvas_w, height=self.canvas_h, bg=self.WHITE, highlightthickness=1, highlightbackground=self.BTN_COLOR)
        self.canvas_pdf.pack()
        self.canvas_pdf.bind("<ButtonPress-1>", self.on_press)
        self.canvas_pdf.bind("<B1-Motion>", self.on_drag)
        self.canvas_pdf.bind("<ButtonRelease-1>", self.on_release)

        # --- Boutons d'action (en bas du panneau droit) ---
        action_frame = tk.Frame(right_frame, bg=self.MENU_BG)
        action_frame.pack(fill=tk.X, pady=(15, 0))
        btn_export = tk.Button(action_frame, text="Exporter PDF", font=("Helvetica", 11, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=20, pady=8, command=self.export_pdf)
        btn_export.pack(side=tk.LEFT, padx=5)
        btn_export.bind("<Enter>", lambda e: btn_export.config(bg=self.BTN_HOVER))
        btn_export.bind("<Leave>", lambda e: btn_export.config(bg=self.BTN_COLOR))

        btn_imprimer = tk.Button(action_frame, text="🖨️ Imprimer", font=("Helvetica", 11, "bold"), bg=self.BTN_COLOR, fg=self.TEXT_COLOR, relief="flat", bd=0, padx=20, pady=8, command=self.imprimer_document)
        btn_imprimer.pack(side=tk.LEFT, padx=5)
        btn_imprimer.bind("<Enter>", lambda e: btn_imprimer.config(bg=self.BTN_HOVER))
        btn_imprimer.bind("<Leave>", lambda e: btn_imprimer.config(bg=self.BTN_COLOR))

        # Initialisation
        self.layers = []
        self.selected_layer_index = -1
        self.update_layer_listbox()
        self.rafraichir_apercu_pdf()

    # --- Gestion des calques ---
    def add_layer(self, layer):
        self.layers.append(layer)
        self.update_layer_listbox()
        self.rafraichir_apercu_pdf()

    def remove_layer(self, index):
        if 0 <= index < len(self.layers):
            del self.layers[index]
            if self.selected_layer_index >= len(self.layers):
                self.selected_layer_index = len(self.layers) - 1
            self.update_layer_listbox()
            self.rafraichir_apercu_pdf()

    def move_layer_up(self):
        idx = self.selected_layer_index
        if idx > 0 and idx < len(self.layers):
            self.layers[idx], self.layers[idx-1] = self.layers[idx-1], self.layers[idx]
            self.selected_layer_index = idx - 1
            self.update_layer_listbox()
            self.rafraichir_apercu_pdf()

    def move_layer_down(self):
        idx = self.selected_layer_index
        if 0 <= idx < len(self.layers) - 1:
            self.layers[idx], self.layers[idx+1] = self.layers[idx+1], self.layers[idx]
            self.selected_layer_index = idx + 1
            self.update_layer_listbox()
            self.rafraichir_apercu_pdf()

    def delete_selected_layer(self):
        idx = self.selected_layer_index
        if idx >= 0 and idx < len(self.layers):
            layer = self.layers[idx]
            if layer.type in ("recto", "verso"):
                layer.image = None
                layer.visible = False
                self.update_layer_listbox()
                self.rafraichir_apercu_pdf()
                return
            self.remove_layer(idx)

    def on_layer_selected(self, event):
        selection = self.listbox_layers.curselection()
        if selection:
            self.selected_layer_index = selection[0]
            layer = self.layers[self.selected_layer_index]
            self.opacity_slider.set(layer.opacity)
        else:
            self.selected_layer_index = -1

    def on_opacity_change(self, value):
        idx = self.selected_layer_index
        if 0 <= idx < len(self.layers):
            self.layers[idx].opacity = float(value)
            self.rafraichir_apercu_pdf()

    def update_layer_listbox(self):
        self.listbox_layers.delete(0, tk.END)
        for i, layer in enumerate(self.layers):
            visible = "✓" if layer.visible else "✗"
            name = layer.name
            self.listbox_layers.insert(tk.END, f"{visible} {name}")
        if self.selected_layer_index >= 0 and self.selected_layer_index < len(self.layers):
            self.listbox_layers.selection_set(self.selected_layer_index)
            self.listbox_layers.activate(self.selected_layer_index)
        else:
            self.selected_layer_index = -1

    def find_layer_by_type(self, layer_type):
        for layer in self.layers:
            if layer.type == layer_type:
                return layer
        return None

    # --- Scan et images ---
    def scan_recto(self):
        self.lbl_img_recto.config(text="Numérisation...")
        self.root.update()
        if self.executer_scan(self.recto_path):
            img = self.detourer_carte(self.recto_path, marge=15)
            layer = self.find_layer_by_type("recto")
            if layer is None:
                layer = Layer("Recto", img, x=100, y=80, opacity=1.0, visible=True, layer_type="recto")
                self.add_layer(layer)
            else:
                layer.image = img
                layer.visible = True
            self.afficher_vignette(img, self.lbl_img_recto)
            self.rafraichir_apercu_pdf()
        else:
            self.lbl_img_recto.config(text="[ Échec ]")

    def scan_verso(self):
        self.lbl_img_verso.config(text="Numérisation...")
        self.root.update()
        if self.executer_scan(self.verso_path):
            img = self.detourer_carte(self.verso_path, marge=15)
            layer = self.find_layer_by_type("verso")
            if layer is None:
                layer = Layer("Verso", img, x=100, y=280, opacity=1.0, visible=True, layer_type="verso")
                self.add_layer(layer)
            else:
                layer.image = img
                layer.visible = True
            self.afficher_vignette(img, self.lbl_img_verso)
            self.rafraichir_apercu_pdf()
        else:
            self.lbl_img_verso.config(text="[ Échec ]")

    def pivoter_carte(self, face):
        layer = self.find_layer_by_type(face)
        if layer and layer.image:
            layer.image = layer.image.rotate(90, expand=True)
            if face == "recto":
                self.afficher_vignette(layer.image, self.lbl_img_recto)
            else:
                self.afficher_vignette(layer.image, self.lbl_img_verso)
            self.rafraichir_apercu_pdf()

    def ajuster_images(self):
        self.rafraichir_apercu_pdf()

    def afficher_vignette(self, im_pil, label_widget):
        im = self.appliquer_luminosite_contraste(im_pil)
        im.thumbnail((150, 100))
        img_tk = ImageTk.PhotoImage(im)
        label_widget.config(image=img_tk, text="")
        label_widget.image = img_tk

    def appliquer_luminosite_contraste(self, im_pil):
        if not im_pil: return None
        lum = self.slider_lum.get()
        cont = self.slider_cont.get()
        im = im_pil.copy()
        enhancer_lum = ImageEnhance.Brightness(im)
        im = enhancer_lum.enhance(lum)
        enhancer_cont = ImageEnhance.Contrast(im)
        im = enhancer_cont.enhance(cont)
        return im

    # --- Détection scanners ---
    def detecter_scanners(self):
        self.combo_scanners.set("Recherche...")
        self.root.update()
        def tache_recherche():
            scanners_trouves = {}
            try:
                resultat = subprocess.run(["scanimage", "-f", "%d|%v %m%n"], capture_output=True, text=True, check=True)
                lignes = [l for l in resultat.stdout.strip().split("\n") if "|" in l]
                for ligne in lignes:
                    dev_id, nom_lisible = ligne.split("|", 1)
                    scanners_trouves[nom_lisible.strip()] = dev_id.strip()
            except Exception:
                pass
            self.root.after(0, self.maj_interface_scanners, scanners_trouves)
        threading.Thread(target=tache_recherche, daemon=True).start()

    def maj_interface_scanners(self, scanners_trouves):
        self.scanners_list = scanners_trouves
        noms = list(self.scanners_list.keys())
        self.combo_scanners['values'] = noms
        if noms:
            if hasattr(self, 'saved_scanner') and self.saved_scanner in noms:
                self.combo_scanners.set(self.saved_scanner)
            else:
                self.combo_scanners.current(0)
        else:
            self.combo_scanners.set("Aucun scanner")

    def obtenir_scanner_selectionne(self):
        nom = self.combo_scanners.get()
        return self.scanners_list.get(nom, None)

    def executer_scan(self, output_path):
        scanner_id = self.obtenir_scanner_selectionne()
        if not scanner_id:
            messagebox.showwarning("Attention", "Sélectionnez un scanner.")
            return False
        choix_source = self.combo_source.get()
        self.sauvegarder_config(afficher_message=False)
        cmd_base = ["scanimage", "-d", scanner_id, "--resolution", "300", "--mode", "Color", "--format=png"]
        cmd_list = []
        if choix_source == "Vitre (Flatbed)":
            cmd_list = [cmd_base + ["--source", "Flatbed"]]
        elif choix_source == "Chargeur auto (ADF)":
            cmd_list = [cmd_base + ["--source", "ADF"]]
        else:
            cmd_list = [cmd_base]
        for index, cmd in enumerate(cmd_list):
            try:
                with open(output_path, "wb") as f:
                    subprocess.run(cmd, stdout=f, check=True)
                return True
            except subprocess.CalledProcessError as e:
                if "busy" in str(e).lower():
                    messagebox.showerror("Scanner occupé", "Le scanner est occupé.")
                    return False
                if index == 0 and len(cmd) > len(cmd_base):
                    try:
                        with open(output_path, "wb") as f:
                            subprocess.run(cmd_base, stdout=f, check=True)
                        return True
                    except subprocess.CalledProcessError:
                        pass
                messagebox.showerror("Erreur", "Scan échoué.")
                return False
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur : {e}")
                return False

    def detourer_carte(self, path_img, marge=15):
        im = Image.open(path_img).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        diff = ImageChops.difference(im, bg).convert("L")
        diff = diff.filter(ImageFilter.MedianFilter(size=5))
        diff = diff.point(lambda x: 255 if x > 30 else 0)
        bbox = diff.getbbox()
        if bbox:
            left = max(0, bbox[0] - marge)
            top = max(0, bbox[1] - marge)
            right = min(im.width, bbox[2] + marge)
            bottom = min(im.height, bbox[3] + marge)
            return im.crop((left, top, right, bottom))
        return im

    # --- Filigrane : création de calques multiples ---
    def on_watermark_type_change(self):
        if self.wm_type_var.get() == "texte":
            self.wm_text_frame.pack(fill=tk.X, pady=2)
            self.wm_image_frame.pack_forget()
        else:
            self.wm_text_frame.pack_forget()
            self.wm_image_frame.pack(fill=tk.X, pady=2)

    def choose_watermark_color(self):
        color = colorchooser.askcolor(title="Couleur", initialcolor=self.watermark_color)
        if color:
            self.watermark_color = color[1]

    def load_watermark_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if path:
            self.watermark_image_path = path

    def clear_watermark_image(self):
        self.watermark_image_path = None

    def get_watermark_params(self):
        texte = self.wm_text_entry.get()
        police = self.combo_font.get()
        try:
            taille = int(self.wm_size_spin.get())
        except:
            taille = 72
        try:
            angle = int(self.wm_angle_spin.get())
        except:
            angle = 0
        return texte, police, taille, angle

    def create_watermark_text(self):
        texte, police, taille, angle = self.get_watermark_params()
        font = None
        font_candidates = [police, "Arial", "Helvetica", "DejaVuSans", "LiberationSans", "Verdana", "Tahoma", "Times New Roman", "Courier New"]
        for fname in font_candidates:
            try:
                font = ImageFont.truetype(fname, taille)
                break
            except:
                continue
        if font is None:
            font = ImageFont.load_default()
            scale = taille / 12.0
        else:
            scale = 1.0

        dummy = Image.new('RGBA', (1,1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0,0), texte, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        img = Image.new('RGBA', (tw + 20, th + 20), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), texte, font=font, fill=self.watermark_color)
        if scale != 1.0:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if angle != 0:
            img = img.rotate(angle, expand=True, resample=Image.BICUBIC)
        return img

    def create_watermark_image(self):
        if not self.watermark_image_path or not os.path.exists(self.watermark_image_path):
            return None
        img = Image.open(self.watermark_image_path).convert("RGBA")
        return img

    def add_watermark_layer(self):
        """Ajoute un nouveau calque de filigrane à partir des paramètres courants."""
        wm_type = self.wm_type_var.get()
        if wm_type == "texte":
            img = self.create_watermark_text()
        else:
            img = self.create_watermark_image()
        if img is None:
            messagebox.showwarning("Attention", "Aucune image de filigrane sélectionnée.")
            return
        # Position au centre
        x = (2480 - img.width) // 2
        y = (3508 - img.height) // 2
        # Générer un nom unique
        count = sum(1 for l in self.layers if l.type == "watermark") + 1
        name = f"Filigrane {count}"
        new_layer = Layer(name, img, x, y, opacity=0.5, visible=True, layer_type="watermark")
        self.add_layer(new_layer)

    # --- Import image comme calque ---
    def import_image_layer(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
            layer = Layer(f"Image {self.next_layer_id}", img, x=100, y=100, opacity=1.0, visible=True, layer_type="custom")
            self.next_layer_id += 1
            self.add_layer(layer)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir l'image : {e}")

    # --- Nettoyage ---
    def clear_scans(self):
        if os.path.exists(self.recto_path): os.remove(self.recto_path)
        if os.path.exists(self.verso_path): os.remove(self.verso_path)
        for layer in self.layers[:]:
            if layer.type in ("recto", "verso"):
                layer.image = None
                layer.visible = False
        self.layers = [l for l in self.layers if l.type in ("recto", "verso", "watermark")]
        for layer in self.layers:
            if layer.type in ("recto", "verso"):
                layer.image = None
                layer.visible = False
        self.lbl_img_recto.config(image='', text="[ Recto ]")
        self.lbl_img_verso.config(image='', text="[ Verso ]")
        self.update_layer_listbox()
        self.rafraichir_apercu_pdf()

    # --- Aperçu et drag & drop ---
    def rafraichir_apercu_pdf(self):
        self.canvas_pdf.delete("all")
        bg = Image.new('RGB', (self.canvas_w, self.canvas_h), 'white')
        for layer in self.layers:
            if not layer.visible or layer.image is None:
                continue
            img = layer.image.copy()
            if layer.type in ("recto", "verso"):
                img = self.appliquer_luminosite_contraste(img)
            new_w = int(img.width * self.scale_factor)
            new_h = int(img.height * self.scale_factor)
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            if layer.opacity < 1.0:
                if img_resized.mode != 'RGBA':
                    img_resized = img_resized.convert('RGBA')
                alpha = int(255 * layer.opacity)
                img_resized.putalpha(alpha)
                bg = bg.convert('RGBA')
                bg.paste(img_resized, (int(layer.x * self.scale_factor), int(layer.y * self.scale_factor)), img_resized)
                bg = bg.convert('RGB')
            else:
                bg.paste(img_resized, (int(layer.x * self.scale_factor), int(layer.y * self.scale_factor)))
        im_tk = ImageTk.PhotoImage(bg)
        self.canvas_pdf.create_image(0, 0, image=im_tk, anchor="nw")
        self.canvas_pdf.image = im_tk

    def on_press(self, event):
        x_canvas = event.x
        y_canvas = event.y
        for idx in range(len(self.layers)-1, -1, -1):
            layer = self.layers[idx]
            if not layer.visible or layer.image is None:
                continue
            x1 = layer.x * self.scale_factor
            y1 = layer.y * self.scale_factor
            w = layer.image.width * self.scale_factor
            h = layer.image.height * self.scale_factor
            if x1 <= x_canvas <= x1 + w and y1 <= y_canvas <= y1 + h:
                self.drag_data["item"] = idx
                self.drag_data["x"] = event.x
                self.drag_data["y"] = event.y
                self.drag_data["layer_index"] = idx
                break

    def on_drag(self, event):
        if self.drag_data["item"] is not None:
            idx = self.drag_data["item"]
            dx = (event.x - self.drag_data["x"]) / self.scale_factor
            dy = (event.y - self.drag_data["y"]) / self.scale_factor
            self.layers[idx].x += dx
            self.layers[idx].y += dy
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.rafraichir_apercu_pdf()

    def on_release(self, event):
        self.drag_data["item"] = None
        self.drag_data["layer_index"] = -1

    # --- Génération PDF et impression ---
    def generer_page_a4(self):
        page = Image.new('RGB', (2480, 3508), 'white')
        for layer in self.layers:
            if not layer.visible or layer.image is None:
                continue
            img = layer.image.copy()
            if layer.type in ("recto", "verso"):
                img = self.appliquer_luminosite_contraste(img)
            if img.mode == 'RGBA':
                page.paste(img, (int(layer.x), int(layer.y)), img)
            else:
                page.paste(img, (int(layer.x), int(layer.y)))
        return page

    def export_pdf(self):
        has_image = any(l.image is not None and l.visible for l in self.layers)
        if not has_image:
            messagebox.showwarning("Attention", "Aucune image à exporter.")
            return
        dossier_initial = self.obtenir_dossier_defaut()
        date_str = datetime.now().strftime("%Y-%m-%d_%Hh%Mm")
        nom_fichier_defaut = f"Carte_Identite_{date_str}.pdf"
        chemin_sauvegarde = filedialog.asksaveasfilename(
            initialdir=dossier_initial,
            initialfile=nom_fichier_defaut,
            defaultextension=".pdf",
            filetypes=[("Fichiers PDF", "*.pdf")],
            title="Sauvegarder le PDF"
        )
        if not chemin_sauvegarde:
            return
        try:
            page_pdf = self.generer_page_a4()
            page_pdf.save(chemin_sauvegarde, "PDF", resolution=300.0)
            messagebox.showinfo("Succès", f"PDF sauvegardé !\n{chemin_sauvegarde}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export : {e}")

    def imprimer_document(self):
        has_image = any(l.image is not None and l.visible for l in self.layers)
        if not has_image:
            messagebox.showwarning("Attention", "Aucune image à imprimer.")
            return
        try:
            page_pdf = self.generer_page_a4()
            page_pdf.save(self.temp_print_pdf, "PDF", resolution=300.0)
            systeme = platform.system().lower()
            if "linux" in systeme:
                try:
                    subprocess.run(["lp", self.temp_print_pdf], check=True)
                    messagebox.showinfo("Impression", "Document envoyé à l'imprimante.")
                except FileNotFoundError:
                    subprocess.run(["lpr", self.temp_print_pdf], check=True)
                    messagebox.showinfo("Impression", "Document envoyé à l'imprimante.")
            elif "windows" in systeme:
                os.startfile(self.temp_print_pdf, "print")
                messagebox.showinfo("Impression", "Document en cours d'impression.")
            else:
                messagebox.showwarning("Impression non supportée", "Impression automatique non disponible.")
        except subprocess.CalledProcessError:
            messagebox.showerror("Erreur d'impression", "Impossible d'envoyer à l'imprimante.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'impression : {e}")

    def obtenir_dossier_defaut(self):
        home_dir = os.path.expanduser("~")
        candidats = ["Documents", "Document", "documents", "document"]
        for nom in candidats:
            chemin_test = os.path.join(home_dir, nom)
            if os.path.exists(chemin_test) and os.path.isdir(chemin_test):
                return chemin_test
        return home_dir

if __name__ == "__main__":
    root = tk.Tk()
    app = ScannerIDApp(root)
    root.mainloop()