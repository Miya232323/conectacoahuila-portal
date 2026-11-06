# -*- coding: utf-8 -*-
"""
Created on Wed Oct 19 01:16:11 2026

@author: Miya
"""

import re
import sqlite3
import secrets
import unicodedata
import random
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_NAME = "ConectaCoahuila"
MAX_MSG_LEN = 1000
DB_FILE = Path.home() / "conectacoahuila.db"

COLOR_PRIMARY = "#0A2540"
COLOR_SECONDARY = "#0066FF"
COLOR_BG = "#F4F6F9"
COLOR_CARD = "#FFFFFF"
COLOR_TEXT_MAIN = "#1E293B"
COLOR_TEXT_MUTED = "#64748B"
COLOR_SUCCESS = "#059669"
COLOR_WARNING = "#D97706"
COLOR_DANGER = "#DC2626"


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def mask_sensitive(text: str) -> str:
    text = re.sub(r"(?i)\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]{2}\b", "[CURP PROTEGIDA]", text)
    text = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[TARJETA PROTEGIDA]", text)
    text = re.sub(r"(?i)(contrasena|password|clave|pin|nip)\s*[:=]?\s*\S+", r"\1 [DATO PROTEGIDO]", text)
    return text[:MAX_MSG_LEN]


class DatabaseManager:
    def __init__(self, path=DB_FILE):
        self.path = str(path)
        self.initialize()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    speed INTEGER NOT NULL,
                    price REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS customers (
                    account TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    balance REAL NOT NULL,
                    region TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT,
                    pin TEXT NOT NULL DEFAULT '1234'
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    folio TEXT PRIMARY KEY,
                    account TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
            """)

            cursor.execute("SELECT COUNT(*) FROM plans")
            if cursor.fetchone()[0] == 0:
                planes_base = [
                    ("P50", "Fibra Esencial Simetrica", 50, 349.00),
                    ("P100", "Fibra Hogar Conectada", 100, 449.00),
                    ("P200", "Fibra Profesional Simetrica", 200, 599.00),
                    ("P500", "Fibra Negocio Ultra", 500, 899.00),
                    ("P1000", "Empresarial Dedicado Giga", 1000, 1499.00),
                ]
                cursor.executemany("INSERT INTO plans VALUES (?, ?, ?, ?)", planes_base)

            cursor.execute("DELETE FROM customers WHERE account LIKE 'CC-%' OR account = '1234'")

            clientes_seed = [
                (
                    "2511891", "Adan Orozco", "P100", 0.00,
                    "Saltillo Poniente", "187.190.45.12", "Activo",
                    "HU#1 (Cliente Principal). Variacion de voltaje. Requiere diagnostico conversacional de ONT.",
                    "1891"
                ),
                (
                    "2511892", "Carlos Rodriguez", "P100", 449.00,
                    "Saltillo Centro", "187.190.45.88", "Activo",
                    "HU#2. Multiples dispositivos en uso y evaluacion de capacidad de ancho de banda.",
                    "1892"
                ),
                (
                    "2511894", "Carlos Rodriguez", "P100", 449.00,
                    "Ramos Arizpe Parque Ind.", "187.190.46.104", "Activo",
                    "HU#3. Solicitud directa de aumento de velocidad y modificacion de contrato (Upgrade).",
                    "1894"
                ),
                (
                    "2511893", "Alberto Mendoza", "P50", 349.00,
                    "Monclova Oriente", "187.190.50.33", "Activo",
                    "HU#4. Desconexiones intermitentes e inestabilidad en el enlace de datos.",
                    "1893"
                ),
                (
                    "2511895", "Sofia Morales", "P500", 0.00,
                    "Arteaga Anillo Dorsal", "187.190.52.19", "Activo",
                    "HU#5. Consulta de falla regional por contingencia climatica en la sierra de Arteaga.",
                    "1895"
                ),
                (
                    "2511896", "Karla Garza", "P200", 599.00,
                    "Torreon Campestre", "187.190.60.22", "Activo",
                    "HU#6. Inconformidad con comportamiento de equipamiento y aclaracion en facturacion.",
                    "1896"
                ),
            ]

            for row in clientes_seed:
                cursor.execute("""
                    INSERT OR REPLACE INTO customers 
                    (account, name, plan_id, balance, region, ip_address, status, notes, pin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, row)

    def authenticate(self, account, pin):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE account = ? AND pin = ?",
                (account.strip().upper(), pin.strip())
            ).fetchone()
            return dict(row) if row else None

    def customer(self, account):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE account = ?", (account.upper(),)).fetchone()
            return dict(row) if row else None

    def plans(self):
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM plans ORDER BY speed")]

    def create_ticket(self, account, category, description):
        folio_str = f"TK-{secrets.token_hex(3).upper()}"
        created = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
                (folio_str, account.upper(), category, description[:500], created, "Abierto"),
            )
        return folio_str

    def tickets(self, account=None):
        with self.connect() as conn:
            if account:
                return [dict(r) for r in conn.execute(
                    "SELECT * FROM tickets WHERE account = ? ORDER BY created_at DESC", (account,)
                )]
            return [dict(r) for r in conn.execute("SELECT * FROM tickets ORDER BY created_at DESC")]

    def pay_balance(self, account):
        with self.connect() as conn:
            conn.execute("UPDATE customers SET balance = 0.0 WHERE account = ?", (account.upper(),))

    def update_plan(self, account, new_plan_id):
        catalogo = {p["plan_id"]: p for p in self.plans()}
        nuevo_precio = catalogo.get(new_plan_id, {"price": 599.0})["price"]
        with self.connect() as conn:
            conn.execute(
                "UPDATE customers SET plan_id = ?, balance = ? WHERE account = ?",
                (new_plan_id, nuevo_precio, account.upper())
            )

    def update_customer_status(self, account, new_status):
        with self.connect() as conn:
            conn.execute("UPDATE customers SET status = ? WHERE account = ?", (new_status, account.upper()))

    def update_ticket_status(self, folio, new_status):
        with self.connect() as conn:
            conn.execute("UPDATE tickets SET status = ? WHERE folio = ?", (new_status, folio))


class ConversationEngine:
    def __init__(self, db, callback=None, telemetry_callback=None):
        self.db = db
        self.callback = callback
        self.telemetry_callback = telemetry_callback
        self.current_account = "2511891"
        self.context_flow = None

    def set_account(self, account):
        self.current_account = account
        self.context_flow = None

    def get_first_name(self):
        c = self.db.customer(self.current_account)
        return c["name"].split()[0] if c else "Estimado suscriptor"

    def get_welcome_message(self):
        c = self.db.customer(self.current_account)
        first_name = self.get_first_name()
        planes = {p["plan_id"]: p for p in self.db.plans()}
        nombre_plan = planes.get(c["plan_id"], {"name": "Fibra Hogar"})["name"] if c else "Fibra Optica"
        region = c["region"] if c else "Coahuila"

        return (
            f"Hola {first_name}, que gusto saludarte. Bienvenido al canal de soporte tecnico de ConectaCoahuila.\n\n"
            f"Tengo en pantalla tu contrato {self.current_account} con {nombre_plan} en el sector {region}. "
            "Cuentame con total libertad, ¿en que te puedo apoyar hoy con tu conexion?"
        )

    def _match(self, text, keywords):
        return any(k in text for k in keywords)

    def handle(self, raw_input):
        text = raw_input.strip()
        n = normalize(text)
        first_name = self.get_first_name()

        if not text:
            return f"Dime {first_name}, ¿en que puedo asistirte el dia de hoy?"
        if len(text) > MAX_MSG_LEN:
            return f"Tu mensaje es un poco extenso. Por favor resúmelo en menos de {MAX_MSG_LEN} caracteres."

        if self._match(n, ["reiniciar chat", "comenzar de nuevo", "inicio", "hola de nuevo", "cancelar proceso"]):
            self.context_flow = None
            return f"Listo {first_name}, he reiniciado nuestra sesion. Dime que situacion deseas que revisemos."

        if n in ("hola", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "que tal", "hola buenas"):
            return (
                f"¡Hola {first_name}! Es un placer atenderte. "
                "Cuentame, ¿presentas alguna falla con tu internet, deseas revisar tu velocidad o necesitas consultar algun detalle de tu contrato?"
            )

        if self._match(n, ["gracias", "muchas gracias", "te agradezco", "excelente gracias"]):
            return f"¡Es un verdadero placer servirte, {first_name}! En ConectaCoahuila estamos disponibles para ti en todo momento. Si necesitas algo mas, aqui estare."

        if self.context_flow == "ont_diagnostic_step":
            if self._match(n, ["rojo", "roja", "los", "parpadea", "foco rojo", "luz roja", "parpadeando"]):
                self.context_flow = "ont_powercycle_step"
                return (
                    f"Entiendo, {first_name}. La luz roja o indicador LOS significa que el equipo esta experimentando "
                    "una perdida en la recepcion de la senal optica.\n\n"
                    "Muchas veces esto se resuelve reiniciando la memoria del dispositivo: por favor, desconecta el cable "
                    "de corriente durante 10 segundos continuos y vuelve a conectarlo firmemente. "
                    "¿Ya lo intentaste o gustas realizarlo en este momento?"
                )
            elif self._match(n, ["apagado", "no prende", "ninguna", "apagadas", "sin luz", "no enciende"]):
                self.context_flow = None
                folio = self.db.create_ticket(
                    self.current_account, "Falla Electrica en ONT (HU#1)",
                    "El suscriptor indica que la ONT no enciende ninguna luz tras variacion de voltaje."
                )
                if self.callback:
                    self.callback()
                return (
                    f"Comprendo, {first_name}. Si no enciende ninguna luz, el problema puede deberse al eliminador de corriente. "
                    f"Por favor valida que el tomacorriente tenga energia. Para no hacerte esperar, te genere la orden tecnica {folio} "
                    "por si se requiere reemplazar el adaptador en tu domicilio."
                )
            else:
                self.context_flow = "ont_powercycle_step"
                return (
                    f"De acuerdo {first_name}. Para descartar desalineacion de la linea, ¿has probado apagar y volver a "
                    "encender el modem desconectandolo 10 segundos de la corriente electrica?"
                )

        if self.context_flow == "ont_powercycle_step":
            self.context_flow = None
            if self._match(n, ["ya", "si", "lo hice", "sigue igual", "no funciona", "no conecta", "continua igual"]):
                folio = self.db.create_ticket(
                    self.current_account, "Reinicio TR-069 Asistido (HU#1)",
                    f"Cliente {first_name} Orozco realizo ciclo de energia sin exito. Envio de paquete de aprovisionamiento OLT."
                )
                if self.telemetry_callback:
                    self.telemetry_callback()
                if self.callback:
                    self.callback()
                return (
                    f"Enterado {first_name}. Como el reinicio fisico manual no restablecio el enlace, acabo de enviar "
                    f"un pulso de sincronizacion forzada directamente a tu ONT mediante protocolo TR-069.\n\n"
                    f"He abierto el folio formal {folio} en nuestra central. Puedes observar como se comunican nuestros "
                    "servidores con tu modem en la pestana 'Diagnostico & Medicion'."
                )
            else:
                return (
                    f"Perfecto {first_name}, hazlo con calma: desconecta el cable de corriente 10 segundos, vuelve a conectarlo "
                    "y espera 1 o 2 minutos a que las luces se estabilicen. Si sigue sin funcionar, escribeme aqui mismo para aplicar un reinicio forzado."
                )

        if self.context_flow == "upgrade_confirmation":
            if self._match(n, ["si", "claro", "adelante", "confirmo", "aceptar", "me interesa", "cambiar", "por favor"]):
                self.context_flow = None
                self.db.update_plan(self.current_account, "P200")
                folio = self.db.create_ticket(
                    self.current_account, "Cambio de Contrato / Upgrade (HU#3)",
                    f"Suscriptor {first_name} autorizo cambio al Plan Fibra Profesional 200 Mbps Simetricos."
                )
                if self.callback:
                    self.callback()
                return (
                    f"¡Excelente noticia, {first_name}! He aplicado el cambio de forma inmediata en el sistema central.\n\n"
                    f"Tu contrato ahora cuenta con el Plan Fibra Profesional de 200 Mbps Simetricos bajo el folio {folio}.\n\n"
                    "Puedes verificar que tu expediente ya muestra los 200 Mbps en la pestana 'Mi Cuenta', y si ejecutas "
                    "la prueba en 'Diagnostico', veras reflejado tu nuevo ancho de banda al instante."
                )
            else:
                self.context_flow = None
                return f"Entendido {first_name}, no te preocupes. Tu plan y tarifa habituales se mantienen sin ninguna modificacion."

        if self._match(n, [
            "no tengo internet", "se fue el internet", "sin conexion", "sin internet", "modem", "ont",
            "luces", "foco rojo", "los", "pon", "voltaje", "variacion de voltaje", "falla el internet", "parpadea"
        ]):
            self.context_flow = "ont_diagnostic_step"
            return (
                f"Lamento mucho el inconveniente con tu conexion, {first_name}. Las variaciones de voltaje a veces desalinean la senal optica.\n\n"
                "Para orientarte con precision: ¿podrias mirar tu modem y decirme que luces tiene encendidas o si notas algun foco parpadeando en rojo?"
            )

        if self._match(n, [
            "aumentar", "upgrade", "mas megas", "subir plan", "cambiar plan", "cambio de contrato",
            "quiero mas velocidad", "paquete mas grande", "mejorar plan", "aumento de velocidad"
        ]):
            self.context_flow = "upgrade_confirmation"
            return (
                f"Con mucho gusto, {first_name}. Actualmente tienes contratados 100 Mbps. "
                "Tengo disponible para aplicacion inmediata nuestro Plan Fibra Profesional Simetrica de 200 Mbps por $599.00 MXN al mes.\n\n"
                "¿Te gustaria que apliquemos la actualizacion en tu linea en este momento?"
            )

        if self._match(n, [
            "ancho de banda", "velocidad tengo", "cuantos megas", "siento lento", "muchos dispositivos",
            "no alcanza", "conectados", "saturacion", "mi velocidad"
        ]):
            cust = self.db.customer(self.current_account)
            planes = {p["plan_id"]: p for p in self.db.plans()}
            p = planes.get(cust["plan_id"], {"name": "Fibra", "speed": 100})
            return (
                f"Con gusto revisamos tu enlace, {first_name}. De acuerdo con el sistema central, tienes contratado el paquete "
                f"{p['name']} con {p['speed']} Mbps de bajada y {p['speed']} Mbps de subida simetrica.\n\n"
                "Cuando hay varios equipos reproduciendo video de alta definicion o realizando descargas a la vez, el ancho de banda "
                "suele saturarse. Si sientes que ya necesitas mayor capacidad, solo dime 'quiero aumentar mi plan' y con gusto lo actualizamos."
            )

        if self._match(n, [
            "intermitente", "se corta", "se va y regresa", "a cada rato", "desconexiones", "inestable",
            "falla parcial", "ayer", "desde ayer", "tarde"
        ]):
            self.db.update_customer_status(self.current_account, "En Monitoreo 24h")
            folio = self.db.create_ticket(
                self.current_account, "Afectacion Parcial de Servicio (HU#4)",
                f"Suscriptor {first_name} reporta desconexiones intermitentes: '{text}'."
            )
            if self.callback:
                self.callback()
            return (
                f"Comprendo lo molesto que resulta tener intermitencia, {first_name}. Cuando la senal se corta y regresa constantemente, "
                "suele deberse a atenuacion o ruido en el cableado exterior de la acometida.\n\n"
                f"Para atenderlo de inmediato:\n"
                f"1. He generado el reporte tecnico {folio} en nuestra mesa de control.\n"
                f"2. Pase el estatus de tu contrato a 'EN MONITOREO 24H' para registrar las caidas de paquetes.\n"
                "3. Se programo una inspeccion fisica de potencia para resolver la inestabilidad."
            )

        if self._match(n, [
            "clima", "lluvia", "tormenta", "falla regional", "mi zona", "mi sector", "arteaga",
            "caida general", "en toda la calle", "masivo"
        ]):
            self.db.update_customer_status(self.current_account, "Afectacion por Clima")
            cust = self.db.customer(self.current_account)
            if self.callback:
                self.callback()
            return (
                f"Te confirmo la situacion, {first_name}. Nuestro Centro de Monitoreo de Red (NOC) reporta una contingencia climatica "
                f"en la troncal dorsal del sector {cust['region']}.\n\n"
                "Se trata de una falla controlada derivada de las recientes tormentas en la zona. Nuestras brigadas de ingenieria "
                "ya se encuentran realizando empalmes en sitio. El estatus de tu linea ha quedado marcado como 'AFECTACION POR CLIMA' "
                "y el servicio se restablecera automaticamente en cuanto concluyan las maniobras."
            )

        if self._match(n, [
            "queja", "inconformidad", "inconforme", "reclamo", "aclaracion", "cobro indebido",
            "cargo", "no funciona mi equipo", "defectuoso", "facturacion"
        ]):
            folio = self.db.create_ticket(
                self.current_account, "Queja / Aclaracion Formal (HU#6)",
                f"Gestion administrativa y de calidad radicada por {first_name}: '{text}'."
            )
            if self.callback:
                self.callback()
            return (
                f"Lamento mucho los inconvenientes que has experimentado, {first_name}. En ConectaCoahuila tu satisfaccion es prioritaria.\n\n"
                f"He formalizado tu inconformidad en el expediente de calidad bajo el folio {folio}.\n"
                "Un supervisor del area de atencion ejecutiva analizara la cronologia de tu caso y se pondra en contacto contigo "
                "en un periodo no mayor a 24 horas habiles para brindarte una solucion puntual."
            )

        if self._match(n, ["saldo", "factura", "cuanto debo", "recibo", "pagar", "corte"]):
            cust = self.db.customer(self.current_account)
            if cust["balance"] <= 0:
                return f"Buenas noticias {first_name}: tu cuenta se encuentra al corriente con saldo en $0.00 MXN."
            return (
                f"Con gusto {first_name}. Tu saldo actual al corte es de ${cust['balance']:.2f} MXN.\n"
                "Puedes liquidarlo facilmente con tu tarjeta registrada desde la pestana 'Mi Cuenta & Servicio'."
            )

        if self._match(n, ["agente", "humano", "asesor", "persona", "telefono", "conmutador"]):
            return (
                f"Por supuesto, {first_name}. Nuestra mesa de soporte telefonico especializada se encuentra a tu disposicion las 24 horas "
                "en el conmutador de Saltillo: 844-411-9000 o al 800-266-3282 sin costo."
            )

        return (
            f"Disculpame {first_name}, no logre captar con precision tu mensaje. "
            "¿Podrias comentarme si tienes problemas de conexion con tu modem, si experimentas lentitud, "
            "o si requieres apoyo con tu plan de velocidad o tu facturacion?"
        )


class ConectaCoahuilaApp:
    def __init__(self, root):
        self.root = root
        self.db = DatabaseManager()
        self.engine = ConversationEngine(
            self.db,
            callback=self.refresh_all_views,
            telemetry_callback=self.simulate_tr069_telemetry
        )
        self.active_account = None

        self.root.title(f"{APP_NAME} - Portal de Gestion de Telecomunicaciones")
        self.root.geometry("1020x760")
        self.root.minsize(940, 680)
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._apply_styles()

        self.container = tk.Frame(self.root, bg=COLOR_BG)
        self.container.pack(fill="both", expand=True)

        self.show_login_screen()

    def on_close(self):
        self.root.destroy()

    def _apply_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Segoe UI", 10), background=COLOR_BG, foreground=COLOR_TEXT_MAIN)
        style.configure("TNotebook", background=COLOR_PRIMARY, tabmargins=[6, 6, 6, 0], borderwidth=0)
        style.configure(
            "TNotebook.Tab", background="#1E3A5F", foreground="white",
            padding=[16, 8], font=("Segoe UI", 10, "bold")
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_CARD)],
            foreground=[("selected", COLOR_PRIMARY)]
        )

        style.configure(
            "Primary.TButton", font=("Segoe UI", 10, "bold"),
            background=COLOR_SECONDARY, foreground="white", borderwidth=0, padding=[12, 6]
        )
        style.map("Primary.TButton", background=[("active", "#0052CC")])

        style.configure(
            "Success.TButton", font=("Segoe UI", 10, "bold"),
            background=COLOR_SUCCESS, foreground="white", borderwidth=0, padding=[12, 6]
        )
        style.map("Success.TButton", background=[("active", "#047857")])

        style.configure(
            "Danger.TButton", font=("Segoe UI", 9, "bold"),
            background=COLOR_DANGER, foreground="white", borderwidth=0, padding=[10, 4]
        )
        style.map("Danger.TButton", background=[("active", "#B91C1C")])

        style.configure(
            "Treeview", font=("Segoe UI", 9), rowheight=26,
            background="white", fieldbackground="white", bordercolor="#CBD5E1"
        )
        style.configure(
            "Treeview.Heading", font=("Segoe UI", 9, "bold"),
            background="#E2E8F0", foreground=COLOR_PRIMARY
        )

    def show_login_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

        self.login_frame = tk.Frame(self.container, bg=COLOR_BG)
        self.login_frame.pack(fill="both", expand=True)

        header = tk.Frame(self.login_frame, bg=COLOR_PRIMARY, height=85)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header, text=APP_NAME.upper(), font=("Segoe UI", 18, "bold"),
            fg="white", bg=COLOR_PRIMARY
        ).pack(pady=(14, 0))
        tk.Label(
            header, text="Portal de Acceso de Suscriptores y Gestion de Servicios",
            font=("Segoe UI", 9), fg="#94A3B8", bg=COLOR_PRIMARY
        ).pack()

        center_area = tk.Frame(self.login_frame, bg=COLOR_BG)
        center_area.pack(expand=True, fill="both")

        card = tk.Frame(center_area, bg=COLOR_CARD, relief="groove", bd=1, padx=45, pady=35)
        card.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(
            card, text="Inicio de Sesion Seguro", font=("Segoe UI", 15, "bold"),
            fg=COLOR_PRIMARY, bg=COLOR_CARD
        ).pack(anchor="w", pady=(0, 20))

        tk.Label(
            card, text="Numero de Contrato:", font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT_MAIN, bg=COLOR_CARD
        ).pack(anchor="w")
        self.entry_contract = ttk.Entry(card, font=("Segoe UI", 11), width=34)
        self.entry_contract.pack(fill="x", pady=(4, 15), ipady=4)
        self.entry_contract.insert(0, "2511894")
        self.entry_contract.focus_set()

        tk.Label(
            card, text="NIP / Clave de Acceso (4 digitos):", font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT_MAIN, bg=COLOR_CARD
        ).pack(anchor="w")
        self.entry_pin = ttk.Entry(card, font=("Segoe UI", 11), width=34, show="*")
        self.entry_pin.pack(fill="x", pady=(4, 22), ipady=4)
        self.entry_pin.insert(0, "1894")
        self.entry_pin.bind("<Return>", lambda e: self.process_login())

        btn_login = ttk.Button(card, text="Ingresar al Sistema", style="Primary.TButton", command=self.process_login)
        btn_login.pack(fill="x", ipady=3)

        footer = tk.Frame(self.login_frame, bg=COLOR_BG, pady=15)
        footer.pack(side="bottom", fill="x")
        tk.Label(
            footer,
            text="ConectaCoahuila Telecomunicaciones S.A. de C.V. | Central Saltillo: 844-411-9000 | Soporte Tecnico 24/7",
            font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG
        ).pack()

    def process_login(self):
        contract = self.entry_contract.get().strip().upper()
        pin = self.entry_pin.get().strip()

        if not contract or not pin:
            messagebox.showwarning("Campos Requeridos", "Debe capturar su Numero de Contrato y NIP de acceso.")
            return

        user = self.db.authenticate(contract, pin)
        if user:
            self.active_account = user["account"]
            self.engine.set_account(self.active_account)
            self.show_portal_screen()
        else:
            messagebox.showerror(
                "Acceso Denegado",
                "Las credenciales ingresadas son incorrectas o el contrato no existe en el sistema."
            )

    def logout(self):
        if messagebox.askyesno("Cerrar Sesion", "¿Desea cerrar la sesion actual del portal?"):
            self.active_account = None
            self.show_login_screen()

    def show_portal_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

        self.portal_frame = tk.Frame(self.container, bg=COLOR_BG)
        self.portal_frame.pack(fill="both", expand=True)

        self._build_header()
        self._build_tabs()
        self.load_customer_data()

    def _build_header(self):
        header = tk.Frame(self.portal_frame, bg=COLOR_PRIMARY, height=72)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        brand_box = tk.Frame(header, bg=COLOR_PRIMARY)
        brand_box.pack(side="left", padx=20, pady=12)

        tk.Label(brand_box, text=APP_NAME.upper(), font=("Segoe UI", 16, "bold"), fg="white", bg=COLOR_PRIMARY).pack(anchor="w")
        tk.Label(brand_box, text="Red Dorsal de Fibra Optica del Estado de Coahuila", font=("Segoe UI", 9), fg="#94A3B8", bg=COLOR_PRIMARY).pack(anchor="w")

        user_box = tk.Frame(header, bg=COLOR_PRIMARY)
        user_box.pack(side="right", padx=20, pady=16)

        self.lbl_user_header = tk.Label(user_box, text="", font=("Segoe UI", 10, "bold"), fg="#CBD5E1", bg=COLOR_PRIMARY)
        self.lbl_user_header.pack(side="left", padx=(0, 15))

        btn_logout = ttk.Button(user_box, text="Cerrar Sesion", style="Danger.TButton", command=self.logout)
        btn_logout.pack(side="left")

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.portal_frame)
        self.notebook.pack(fill="both", expand=True)

        self.tab_account = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_account, text=" Mi Cuenta & Servicio ")
        self._build_account_tab()

        self.tab_chat = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_chat, text=" Asistente de Atencion ")
        self._build_chat_tab()

        self.tab_diag = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_diag, text=" Diagnostico & Medicion ")
        self._build_diag_tab()

        self.tab_tickets = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_tickets, text=" Centro de Folios (SLA) ")
        self._build_tickets_tab()

        self.tab_network = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_network, text=" Estado de Red ")
        self._build_network_tab()

    def _build_account_tab(self):
        container = tk.Frame(self.tab_account, bg=COLOR_BG, padx=25, pady=20)
        container.pack(fill="both", expand=True)

        kpi_row = tk.Frame(container, bg=COLOR_BG)
        kpi_row.pack(fill="x", pady=(0, 20))

        c1 = tk.Frame(kpi_row, bg=COLOR_CARD, relief="groove", bd=1, padx=20, pady=16)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(c1, text="PLAN CONTRATADO", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.lbl_plan_name = tk.Label(c1, text="--", font=("Segoe UI", 14, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD)
        self.lbl_plan_name.pack(anchor="w", pady=4)
        self.lbl_plan_speed = tk.Label(c1, text="-- Mbps", font=("Segoe UI", 10), fg=COLOR_SECONDARY, bg=COLOR_CARD)
        self.lbl_plan_speed.pack(anchor="w")

        c2 = tk.Frame(kpi_row, bg=COLOR_CARD, relief="groove", bd=1, padx=20, pady=16)
        c2.pack(side="left", fill="both", expand=True, padx=10)
        tk.Label(c2, text="ESTATUS DE CONEXION", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.lbl_ont_status = tk.Label(c2, text="ACTIVO", font=("Segoe UI", 13, "bold"), fg=COLOR_SUCCESS, bg=COLOR_CARD)
        self.lbl_ont_status.pack(anchor="w", pady=4)
        self.lbl_ont_ip = tk.Label(c2, text="IP: --", font=("Segoe UI", 10), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD)
        self.lbl_ont_ip.pack(anchor="w")

        c3 = tk.Frame(kpi_row, bg=COLOR_CARD, relief="groove", bd=1, padx=20, pady=16)
        c3.pack(side="left", fill="both", expand=True, padx=(10, 0))
        tk.Label(c3, text="SALDO EXIGIBLE", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD).pack(anchor="w")
        self.lbl_balance = tk.Label(c3, text="$0.00 MXN", font=("Segoe UI", 14, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD)
        self.lbl_balance.pack(anchor="w", pady=4)
        self.btn_pay = ttk.Button(c3, text="Pagar Factura", style="Success.TButton", command=self.action_pay_bill)
        self.btn_pay.pack(anchor="w", pady=(2, 0))

        main_card = tk.Frame(container, bg=COLOR_CARD, relief="groove", bd=1, padx=25, pady=20)
        main_card.pack(fill="both", expand=True)

        tk.Label(
            main_card, text="Expediente de Servicio GPON / FTTH",
            font=("Segoe UI", 12, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD
        ).pack(anchor="w", pady=(0, 15))

        self.lbl_details = tk.Label(main_card, text="", font=("Segoe UI", 10), justify="left", fg=COLOR_TEXT_MAIN, bg=COLOR_CARD)
        self.lbl_details.pack(anchor="w")

        tk.Label(
            main_card, text="Consumo Mensual Acumulado: 418 GB transferidos (Sin restriccion de volumen)",
            font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD
        ).pack(anchor="w", pady=(25, 6))

        self.progress_usage = ttk.Progressbar(main_card, orient="horizontal", mode="determinate", value=52)
        self.progress_usage.pack(fill="x", ipady=3)

    def load_customer_data(self):
        c = self.db.customer(self.active_account)
        if not c:
            return

        planes = {p["plan_id"]: p for p in self.db.plans()}
        plan = planes.get(c["plan_id"], {"name": "No asignado", "speed": 0, "price": 0.0})

        self.lbl_user_header.config(text=f"Sesion: {c['name']} ({c['account']}) | [{c['status'].upper()}]")
        self.lbl_plan_name.config(text=plan["name"])
        self.lbl_plan_speed.config(text=f"Ancho de banda: {plan['speed']} Mbps Simetricos")
        self.lbl_ont_ip.config(text=f"Direccion IP ONT: {c['ip_address']}")

        if c["status"] == "Activo":
            self.lbl_ont_status.config(text="EN LINEA / NORMAL", fg=COLOR_SUCCESS)
        elif "Monitoreo" in c["status"]:
            self.lbl_ont_status.config(text="EN MONITOREO 24H", fg=COLOR_WARNING)
        else:
            self.lbl_ont_status.config(text=c["status"].upper(), fg=COLOR_DANGER)

        self.lbl_balance.config(
            text=f"${c['balance']:.2f} MXN",
            fg=COLOR_DANGER if c["balance"] > 0 else COLOR_SUCCESS
        )

        detalles = (
            f"- Suscriptor Titular: {c['name']}\n"
            f"- Identificador de Contrato: {c['account']}\n"
            f"- Sector / Cobertura: {c['region']}\n"
            f"- Tarifa Mensual: ${plan['price']:.2f} MXN con impuestos incluidos\n"
            f"- Dia de Facturacion: 15 de cada mes\n"
            f"- Caso de Estudio Asignado: {c.get('notes', 'Sin incidencias')}\n"
        )
        self.lbl_details.config(text=detalles)

    def action_pay_bill(self):
        c = self.db.customer(self.active_account)
        if not c:
            return
        if c["balance"] <= 0:
            messagebox.showinfo("Facturacion", "La cuenta se encuentra al corriente sin saldos vencidos.")
            return

        if messagebox.askyesno("Confirmacion de Pago", f"¿Desea procesar el pago de ${c['balance']:.2f} MXN para la cuenta {c['account']}?"):
            self.db.pay_balance(self.active_account)
            self.load_customer_data()
            messagebox.showinfo("Transaccion Exitosa", f"Cargo aplicado correctamente por ${c['balance']:.2f} MXN.")
            self.append_chat_message("bot", f"Confirmacion: Se recibio el pago de ${c['balance']:.2f} MXN. Saldo actualizado.")

    def _build_chat_tab(self):
        container = tk.Frame(self.tab_chat, bg=COLOR_BG, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        card = tk.Frame(container, bg=COLOR_CARD, relief="groove", bd=1)
        card.pack(fill="both", expand=True)

        self.chat_box = tk.Text(
            card, wrap="word", state="disabled", font=("Segoe UI", 10),
            bg="white", relief="flat", padx=16, pady=16
        )
        self.chat_box.pack(fill="both", expand=True)

        self.chat_box.tag_config("bot_title", foreground=COLOR_PRIMARY, font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("bot_text", foreground=COLOR_TEXT_MAIN, lmargin1=10, lmargin2=10)
        self.chat_box.tag_config("user_title", foreground=COLOR_SECONDARY, font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("user_text", foreground="#0F172A", lmargin1=10, lmargin2=10)

        bar_quick = tk.Frame(card, bg="#F1F5F9", padx=10, pady=6)
        bar_quick.pack(fill="x")

        atajos = [
            ("Reinicio de Modem", "Tengo problemas con el modem y la luz roja"),
            ("Aumentar Velocidad", "Quiero aumentar mi velocidad a un plan mas grande"),
            ("Consulta de Ancho de Banda", "Siento que el internet no me alcanza con tantos equipos"),
            ("Falla e Intermitencia", "Tengo desconexiones intermitentes desde ayer"),
            ("Falla por Clima", "Creo que hay una falla general en mi sector por la tormenta"),
            ("Presentar Queja", "Quiero poner una queja por fallas en mis equipos"),
        ]
        for label, prompt in atajos:
            btn = tk.Button(
                bar_quick, text=label, font=("Segoe UI", 8, "bold"), bg="white",
                fg=COLOR_PRIMARY, relief="solid", bd=1, cursor="hand2", padx=8, pady=3,
                command=lambda p=prompt: self.process_message(p)
            )
            btn.pack(side="left", padx=3)

        bar_input = tk.Frame(card, bg=COLOR_CARD, padx=12, pady=10)
        bar_input.pack(fill="x", side="bottom")

        self.input_entry = ttk.Entry(bar_input, font=("Segoe UI", 10))
        self.input_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.input_entry.bind("<Return>", lambda e: self.send_message())

        ttk.Button(bar_input, text="Enviar Mensaje", style="Primary.TButton", command=self.send_message).pack(side="left", padx=4)
        ttk.Button(bar_input, text="Exportar Chat", command=self.export_chat_log).pack(side="left", padx=2)

        self.append_chat_message("bot", self.engine.get_welcome_message())

    def append_chat_message(self, role, text):
        self.chat_box.configure(state="normal")
        now = datetime.now().strftime("%H:%M")
        if role == "user":
            self.chat_box.insert("end", f"Tu ({self.active_account}) - {now}\n", "user_title")
            self.chat_box.insert("end", f"{text}\n\n", "user_text")
        else:
            self.chat_box.insert("end", f"Asistente Virtual ConectaCoahuila - {now}\n", "bot_title")
            self.chat_box.insert("end", f"{text}\n\n", "bot_text")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def send_message(self):
        text = self.input_entry.get().strip()
        if text:
            self.input_entry.delete(0, "end")
            self.process_message(text)

    def process_message(self, text):
        limpio = mask_sensitive(text)
        self.append_chat_message("user", limpio)
        self.root.after(100, lambda: self.reply_from_engine(limpio))

    def reply_from_engine(self, text):
        respuesta = self.engine.handle(text)
        self.append_chat_message("bot", respuesta)

    def export_chat_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivo de Registro", "*.txt")],
            title="Exportar Historial de Atencion"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.chat_box.get("1.0", "end-1c"))
                messagebox.showinfo("Registro Guardado", "El expediente fue exportado exitosamente.")
            except Exception as e:
                messagebox.showerror("Error al Guardar", f"No se pudo guardar el archivo: {e}")

    def _build_diag_tab(self):
        container = tk.Frame(self.tab_diag, bg=COLOR_BG, padx=25, pady=15)
        container.pack(fill="both", expand=True)

        card = tk.Frame(container, bg=COLOR_CARD, relief="groove", bd=1, padx=25, pady=18)
        card.pack(fill="both", expand=True)

        tk.Label(
            card, text="Diagnostico de Canal Optico y Telemetria en Tiempo Real",
            font=("Segoe UI", 12, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD
        ).pack(anchor="w")

        metrics_frame = tk.Frame(card, bg=COLOR_CARD)
        metrics_frame.pack(fill="x", pady=8)

        self.box_ping = self._build_metric_tile(metrics_frame, "LATENCIA / PING", "-- ms", 0)
        self.box_jitter = self._build_metric_tile(metrics_frame, "JITTER", "-- ms", 1)
        self.box_down = self._build_metric_tile(metrics_frame, "TASA DE BAJADA", "-- Mbps", 2)
        self.box_up = self._build_metric_tile(metrics_frame, "TASA DE SUBIDA", "-- Mbps", 3)

        self.diag_progress = ttk.Progressbar(card, orient="horizontal", mode="determinate")
        self.diag_progress.pack(fill="x", pady=10, ipady=2)

        btn_row = tk.Frame(card, bg=COLOR_CARD)
        btn_row.pack(pady=4)

        self.btn_start_diag = ttk.Button(btn_row, text="Ejecutar Prueba de Capacidad", style="Primary.TButton", command=self.execute_diagnostics)
        self.btn_start_diag.pack(side="left", padx=8)

        self.btn_reset_ont = ttk.Button(btn_row, text="Reinicio Remoto TR-069", command=self.simulate_tr069_telemetry)
        self.btn_reset_ont.pack(side="left", padx=8)

        tk.Label(
            card, text="Consola de Telemetria OLT / Protocolo TR-069 (CWMP):",
            font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_CARD
        ).pack(anchor="w", pady=(12, 2))

        self.telemetry_terminal = tk.Text(
            card, height=7, font=("Consolas", 8), bg="#0F172A",
            fg="#10B981", relief="flat", padx=10, pady=8
        )
        self.telemetry_terminal.pack(fill="x", expand=False)
        self.log_telemetry("Sistema de telemetria inicializado. Enlace con OLT Saltillo listo.")

    def log_telemetry(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.telemetry_terminal.insert("end", f"[{now}] {msg}\n")
        self.telemetry_terminal.see("end")

    def _build_metric_tile(self, parent, title, init_val, col):
        frame = tk.Frame(parent, bg="#F8FAFC", relief="solid", bd=1, padx=12, pady=8)
        frame.grid(row=0, column=col, padx=6, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(frame, text=title, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg="#F8FAFC").pack()
        lbl = tk.Label(frame, text=init_val, font=("Segoe UI", 13, "bold"), fg=COLOR_PRIMARY, bg="#F8FAFC")
        lbl.pack(pady=2)
        return lbl

    def execute_diagnostics(self):
        c = self.db.customer(self.active_account)
        planes = {p["plan_id"]: p for p in self.db.plans()}
        speed = planes.get(c["plan_id"], {"speed": 100})["speed"]

        self.btn_start_diag.config(state="disabled")
        self.diag_progress["value"] = 0
        self.log_telemetry(f"Iniciando medicion de canal contra IXP Coahuila para contrato {c['account']}...")

        def _step(idx=0):
            if idx == 1:
                self.box_ping.config(text=f"{random.randint(9, 14)} ms")
                self.box_jitter.config(text=f"{random.randint(1, 3)} ms")
                self.diag_progress["value"] = 35
                self.log_telemetry("Sondeo TCP establecido. Transfiriendo paquetes de prueba...")
                self.root.after(600, lambda: _step(2))
            elif idx == 2:
                down = round(speed * random.uniform(0.97, 1.02), 1)
                self.box_down.config(text=f"{down} Mbps")
                self.diag_progress["value"] = 75
                self.log_telemetry(f"Tasa de bajada registrada: {down} Mbps (Capacidad nominal: {speed} Mbps).")
                self.root.after(600, lambda: _step(3))
            elif idx == 3:
                up = round(speed * random.uniform(0.96, 1.01), 1)
                self.box_up.config(text=f"{up} Mbps")
                self.diag_progress["value"] = 100
                self.log_telemetry(f"Tasa de subida simetrica: {up} Mbps. Prueba completada exitosamente.")
                self.btn_start_diag.config(state="normal")
            else:
                self.root.after(300, lambda: _step(1))

        _step(0)

    def simulate_tr069_telemetry(self):
        c = self.db.customer(self.active_account)
        ip = c["ip_address"] if c else "187.190.45.12"
        self.btn_reset_ont.config(state="disabled")

        def _trace(step_idx=0):
            if step_idx == 0:
                self.log_telemetry(f"[TR-069] Estableciendo sesion CWMP con ONT en {ip}:7547...")
                self.root.after(700, lambda: _trace(1))
            elif step_idx == 1:
                self.log_telemetry("[TR-069] Autenticacion completada. RPC Method: Device.ManagementServer.Reboot()")
                self.root.after(800, lambda: _trace(2))
            elif step_idx == 2:
                self.log_telemetry("[OLT-CORE] Dispositivo reiniciado. Sincronizando longitud de onda GPON...")
                self.root.after(900, lambda: _trace(3))
            elif step_idx == 3:
                self.log_telemetry("[OLT-CORE] Potencia optica de recepcion Rx: -18.9 dBm [Optima / Normal].")
                self.log_telemetry("[SISTEMA] Enlace de fibra optica sincronizado satisfactoriamente.")
                self.btn_reset_ont.config(state="normal")
                self.load_customer_data()

        _trace(0)

    def _build_tickets_tab(self):
        container = tk.Frame(self.tab_tickets, bg=COLOR_BG, padx=25, pady=20)
        container.pack(fill="both", expand=True)

        top_row = tk.Frame(container, bg=COLOR_BG)
        top_row.pack(fill="x", pady=(0, 12))

        tk.Label(
            top_row, text="Control de Incidencias y Acuerdos de Nivel de Servicio (SLA)",
            font=("Segoe UI", 12, "bold"), fg=COLOR_PRIMARY, bg=COLOR_BG
        ).pack(side="left")

        ttk.Button(top_row, text="Aperturar Nuevo Folio", style="Primary.TButton", command=self.open_new_ticket_dialog).pack(side="right")

        table_card = tk.Frame(container, bg=COLOR_CARD, relief="groove", bd=1)
        table_card.pack(fill="both", expand=True)

        columnas = ("folio", "account", "category", "created_at", "status")
        self.tickets_tree = ttk.Treeview(table_card, columns=columnas, show="headings", selectmode="browse")

        self.tickets_tree.heading("folio", text="Folio")
        self.tickets_tree.heading("account", text="Contrato")
        self.tickets_tree.heading("category", text="Tipo de Incidencia")
        self.tickets_tree.heading("created_at", text="Fecha de Registro")
        self.tickets_tree.heading("status", text="Estatus SLA")

        self.tickets_tree.column("folio", width=90, anchor="center")
        self.tickets_tree.column("account", width=100, anchor="center")
        self.tickets_tree.column("category", width=220, anchor="w")
        self.tickets_tree.column("created_at", width=140, anchor="center")
        self.tickets_tree.column("status", width=110, anchor="center")

        scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tickets_tree.yview)
        self.tickets_tree.configure(yscrollcommand=scroll.set)
        self.tickets_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bottom_actions = tk.Frame(container, bg=COLOR_BG)
        bottom_actions.pack(fill="x", pady=10)

        ttk.Button(bottom_actions, text="Consultar Descripcion", command=self.view_selected_ticket).pack(side="left", padx=5)
        ttk.Button(bottom_actions, text="Concluir Folio", command=self.resolve_current_ticket).pack(side="left", padx=5)

        self.refresh_tickets_table()

    def refresh_tickets_table(self):
        for item in self.tickets_tree.get_children():
            self.tickets_tree.delete(item)

        for t in self.db.tickets():
            self.tickets_tree.insert("", "end", values=(
                t["folio"], t["account"], t["category"], t["created_at"], t["status"]
            ))

    def refresh_all_views(self):
        self.load_customer_data()
        self.refresh_tickets_table()

    def view_selected_ticket(self):
        sel = self.tickets_tree.selection()
        if not sel:
            messagebox.showwarning("Seleccion Requerida", "Seleccione un folio de la tabla.")
            return

        folio = self.tickets_tree.item(sel[0])["values"][0]

        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE folio = ?", (folio,)).fetchone()
            if row:
                t = dict(row)
                messagebox.showinfo(
                    f"Expediente Tecnico {t['folio']}",
                    f"Folio: {t['folio']}\n"
                    f"Contrato: {t['account']}\n"
                    f"Categoria: {t['category']}\n"
                    f"Fecha: {t['created_at']}\n"
                    f"Estatus: {t['status']}\n\n"
                    f"Descripcion:\n{t['description']}"
                )

    def resolve_current_ticket(self):
        sel = self.tickets_tree.selection()
        if not sel:
            messagebox.showwarning("Seleccion Requerida", "Seleccione un folio para cambiar su estatus.")
            return

        folio = self.tickets_tree.item(sel[0])["values"][0]
        self.db.update_ticket_status(folio, "Resuelto")
        self.refresh_tickets_table()
        messagebox.showinfo("Folio Actualizado", f"El folio {folio} fue marcado como Resuelto.")

    def open_new_ticket_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Registro de Incidencia Tecnica")
        win.geometry("460x390")
        win.resizable(False, False)
        win.configure(bg=COLOR_BG)
        win.grab_set()

        tk.Label(
            win, text="Apertura de Reporte Tecnico", font=("Segoe UI", 12, "bold"),
            fg=COLOR_PRIMARY, bg=COLOR_BG
        ).pack(pady=12)

        body = tk.Frame(win, bg=COLOR_BG, padx=25)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Clasificacion de la Incidencia:", font=("Segoe UI", 9, "bold"), bg=COLOR_BG).pack(anchor="w")
        cat_box = ttk.Combobox(body, state="readonly", values=[
            "Reinicio y Alineacion ONT (HU#1)",
            "Consulta de Ancho de Banda (HU#2)",
            "Cambio de Contrato (HU#3)",
            "Falla Parcial / Intermitencia (HU#4)",
            "Falla Regional por Clima (HU#5)",
            "Queja o Aclaracion Formal (HU#6)",
        ])
        cat_box.current(0)
        cat_box.pack(fill="x", pady=(2, 10))

        tk.Label(body, text="Detalle y Descripcion de Campo:", font=("Segoe UI", 9, "bold"), bg=COLOR_BG).pack(anchor="w")
        txt_desc = tk.Text(body, height=6, font=("Segoe UI", 9))
        txt_desc.pack(fill="x", pady=(2, 15))

        def _commit():
            desc = txt_desc.get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Validacion", "Debe capturar los detalles tecnicos.", parent=win)
                return
            folio = self.db.create_ticket(self.active_account, cat_box.get(), desc)
            self.refresh_tickets_table()
            win.destroy()
            messagebox.showinfo("Folio Generado", f"El reporte {folio} se registro formalmente.")
            self.append_chat_message("bot", f"Se abrio el folio {folio} correspondiente a {cat_box.get()}.")

        ttk.Button(body, text="Registrar en Bitacora", style="Primary.TButton", command=_commit).pack(fill="x")

    def _build_network_tab(self):
        container = tk.Frame(self.tab_network, bg=COLOR_BG, padx=30, pady=25)
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Centro de Operaciones de Red (NOC Coahuila)", font=("Segoe UI", 13, "bold"), fg=COLOR_PRIMARY, bg=COLOR_BG).pack(anchor="w")
        tk.Label(container, text="Monitoreo en tiempo real de nodos de agregacion, troncales y anillos de fibra optica.", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG).pack(anchor="w", pady=(0, 20))

        card = tk.Frame(container, bg=COLOR_CARD, relief="groove", bd=1, padx=25, pady=20)
        card.pack(fill="both", expand=True)

        nodos = [
            ("Nodo Saltillo Centro (Core IXP)", "99.99%", "OPERATIVO", "8 ms", COLOR_SUCCESS),
            ("Nodo Saltillo Poniente (Sector Adan Orozco)", "99.98%", "OPERATIVO", "10 ms", COLOR_SUCCESS),
            ("Nodo Ramos Arizpe Industrial (Sector Carlos 2)", "99.95%", "OPERATIVO", "11 ms", COLOR_SUCCESS),
            ("Anillo Troncal Arteaga (Sector Sofia Morales)", "94.20%", "AFECTACION POR CLIMA", "38 ms", COLOR_WARNING),
            ("Nodo Monclova Oriente (Sector Alberto Mendoza)", "97.80%", "INTERMITENCIA PARCIAL", "24 ms", COLOR_WARNING),
            ("Troncal Laguna - Torreon Campestre (Sector Karla Garza)", "99.96%", "OPERATIVO", "16 ms", COLOR_SUCCESS),
        ]

        for nombre, sla, status, lat, color in nodos:
            row = tk.Frame(card, bg="white", pady=10)
            row.pack(fill="x", pady=3)

            tk.Label(row, text=nombre, font=("Segoe UI", 10, "bold"), fg=COLOR_PRIMARY, bg="white").pack(side="left")
            tk.Label(row, text=f"Latencia Media: {lat}  |  SLA Mensual: {sla}", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg="white").pack(side="right", padx=15)
            tk.Label(row, text=f"[{status}]", font=("Segoe UI", 9, "bold"), fg=color, bg="white").pack(side="right")


def main():
    root = tk.Tk()
    ConectaCoahuilaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
