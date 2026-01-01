import customtkinter as ctk
import sqlite3
import datetime
import pandas as pd
import shutil
import os
import winsound  # Standard Windows library for beep sounds
from tkinter import messagebox, filedialog
import tkinter

# --- BRANDING & CONSTANTS ---
SHOP_NAME = "Smart-Attendance-System"
DB_FILE = "sharp_system_master.db"

# --- THEME ENGINE (Modern Slate & Indigo) ---
class Theme:
    BG_MAIN = "#0f172a"      # Deep Navy Background
    BG_SIDE = "#1e293b"      # Sidebar Slate
    CARD    = "#1e293b"      # Card Background
    ACCENT  = "#6366f1"      # Indigo Primary Button
    HOVER   = "#4f46e5"      # Indigo Hover
    DANGER  = "#ef4444"      # Red
    SUCCESS = "#10b981"      # Emerald Green
    TEXT    = "#f8fafc"      # White
    TEXT_DIM= "#94a3b8"      # Gray
    BORDER  = "#334155"      # Border Lines

class Database:
    def __init__(self):
        self.path = DB_FILE
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute("PRAGMA foreign_keys = ON")
            # Staff Table
            c.execute('''CREATE TABLE IF NOT EXISTS staff 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         name TEXT, pin TEXT UNIQUE, 
                         role TEXT, job_type TEXT, start_time TEXT)''')
            # Logs Table (Cascading Delete: If staff deleted, logs go too)
            c.execute('''CREATE TABLE IF NOT EXISTS logs 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         staff_id INTEGER, date TEXT, t_in TEXT, t_out TEXT, status TEXT,
                         FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE)''')
            # Config Table
            c.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, val TEXT)''')
            
            # Defaults
            if not self.fetch("SELECT * FROM config WHERE key='admin_pin'"):
                c.execute("INSERT INTO config VALUES ('admin_pin', '0000')")
            if not self.fetch("SELECT * FROM config WHERE key='grace_period'"):
                c.execute("INSERT INTO config VALUES ('grace_period', '15')")

    def fetch(self, sql, params=()):
        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def commit(self, sql, params=()):
        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(sql, params)
            conn.commit()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.title(f"{SHOP_NAME} // Manager")
        self.geometry("1300x850")
        ctk.set_appearance_mode("Dark")
        self.configure(fg_color=Theme.BG_MAIN)
        
        self.view = "LOGIN"
        self.active_frame = None
        self.edit_mode_id = None 
        self.filter_date = datetime.datetime.now().strftime("%Y-%m-%d")

        self.bind("<Key>", self._on_key)
        self.show_login()

    def _on_key(self, event):
        # Global Keyboard Handler for Numpad support
        if self.view in ["LOGIN", "TERMINAL"]:
            if event.char.isdigit(): self._input_handler(event.char)
            elif event.keysym in ["Return", "KP_Enter"]: self._input_handler("ENTER")
            elif event.keysym in ["BackSpace", "Delete"]: self._input_handler("CLR")

    def clear(self):
        if self.active_frame: self.active_frame.destroy()

    # ==========================
    # 🔒 1. LOGIN SCREEN
    # ==========================
    def show_login(self):
        self.clear(); self.view = "LOGIN"
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        self.active_frame = container

        ctk.CTkLabel(container, text="SYSTEM LOCKED", font=("Inter", 14, "bold"), text_color=Theme.ACCENT).pack(pady=5)
        ctk.CTkLabel(container, text=SHOP_NAME, font=("Inter", 32, "bold"), text_color=Theme.TEXT).pack(pady=(0,30))

        self.pin_entry = ""
        self.lbl_pin = ctk.CTkLabel(container, text="Enter PIN", font=("Consolas", 32), text_color=Theme.TEXT_DIM)
        self.lbl_pin.pack(pady=20)

        # Numpad
        pad = ctk.CTkFrame(container, fg_color="transparent"); pad.pack()
        keys = ['1','2','3','4','5','6','7','8','9','CLR','0','➜']
        for i, k in enumerate(keys):
            ctk.CTkButton(pad, text=k, width=80, height=80, corner_radius=20, 
                          fg_color=Theme.BG_SIDE, hover_color=Theme.BORDER, text_color=Theme.TEXT,
                          font=("Inter", 20, "bold"), command=lambda x=k: self._input_handler(x)).grid(row=i//3, column=i%3, padx=8, pady=8)

    def _input_handler(self, val):
        if self.view == "LOGIN":
            if val == "CLR": self.pin_entry = ""
            elif val == "ENTER": self._check_admin_login()
            elif val.isdigit() and len(self.pin_entry) < 4: self.pin_entry += val
            self._update_login_display()
            
        elif self.view == "TERMINAL":
            if val == "CLR": self.term_pin = self.term_pin[:-1] # Backspace behavior
            elif val.isdigit() and len(self.term_pin) < 4: self.term_pin += val
            self._update_term_display()

    def _update_login_display(self):
        # Check if we're still on login screen and label exists
        if self.view != "LOGIN" or not hasattr(self, 'lbl_pin'):
            return
        try:
            mask = "•" * len(self.pin_entry) if self.pin_entry else "Enter PIN"
            self.lbl_pin.configure(text=mask, text_color=Theme.TEXT if self.pin_entry else Theme.TEXT_DIM)
        except (AttributeError, tkinter.TclError):
            # Widget was destroyed, ignore
            pass

    def _check_admin_login(self):
        admin_pin = self.db.fetch("SELECT val FROM config WHERE key='admin_pin'")[0][0]
        if self.pin_entry == admin_pin:
            self.show_dashboard()
        else:
            if self.view == "LOGIN" and hasattr(self, 'lbl_pin'):
                try:
                    self.lbl_pin.configure(text="ACCESS DENIED", text_color=Theme.DANGER)
                except (AttributeError, tkinter.TclError):
                    pass
            self.pin_entry = ""
            self.after(1000, self._update_login_display)

    # ==========================
    # 📊 2. MAIN DASHBOARD
    # ==========================
    def show_dashboard(self):
        self.clear(); self.view = "ADMIN"
        
        # Layout: Sidebar + Main Content
        wrapper = ctk.CTkFrame(self, fg_color=Theme.BG_MAIN); wrapper.pack(fill="both", expand=True)
        self.active_frame = wrapper
        
        # Sidebar
        side = ctk.CTkFrame(wrapper, width=260, fg_color=Theme.BG_SIDE, corner_radius=0)
        side.pack(side="left", fill="y")
        
        ctk.CTkLabel(side, text=SHOP_NAME, font=("Inter", 18, "bold"), text_color=Theme.TEXT).pack(pady=(40,40), padx=25, anchor="w")
        self._nav_btn(side, "📊  Overview", self.render_overview)
        self._nav_btn(side, "👥  Staff Hub", self.render_staff)
        self._nav_btn(side, "⚙️  System", self.render_settings)
        
        ctk.CTkButton(side, text="LAUNCH TERMINAL", height=50, fg_color=Theme.ACCENT, hover_color=Theme.HOVER, 
                      font=("Inter", 14, "bold"), command=self.launch_terminal).pack(side="bottom", fill="x", padx=20, pady=20)
        
        ctk.CTkButton(side, text="🔒 Lock", height=30, fg_color="transparent", text_color=Theme.DANGER, 
                      hover_color=Theme.BG_MAIN, command=self.show_login).pack(side="bottom", fill="x", padx=20, pady=0)

        # Content Area
        self.content = ctk.CTkFrame(wrapper, fg_color="transparent")
        self.content.pack(side="right", fill="both", expand=True, padx=30, pady=30)
        self.render_overview()

    def _nav_btn(self, parent, txt, cmd):
        ctk.CTkButton(parent, text=txt, height=45, anchor="w", fg_color="transparent", hover_color=Theme.BG_MAIN, 
                      text_color=Theme.TEXT_DIM, font=("Inter", 15), command=cmd).pack(fill="x", padx=10, pady=5)

    # --- DASHBOARD: OVERVIEW ---
    def render_overview(self):
        for w in self.content.winfo_children(): w.destroy()
        
        # Header
        head = ctk.CTkFrame(self.content, fg_color="transparent"); head.pack(fill="x", pady=(0,20))
        ctk.CTkLabel(head, text="Attendance Overview", font=("Inter", 26, "bold"), text_color=Theme.TEXT).pack(side="left")
        
        # Date Filter
        ctk.CTkButton(head, text="↻", width=40, fg_color=Theme.BG_SIDE, command=self.render_overview).pack(side="right", padx=5)
        self.date_picker = ctk.CTkEntry(head, width=120, fg_color=Theme.BG_SIDE, border_width=0, text_color=Theme.TEXT)
        self.date_picker.pack(side="right"); self.date_picker.insert(0, self.filter_date)
        ctk.CTkButton(head, text="Set Date", width=80, fg_color=Theme.ACCENT, command=lambda: [setattr(self,'filter_date',self.date_picker.get()), self.render_overview()]).pack(side="right", padx=10)

        # Logic: Only count CURRENT staff logs
        logs = self.db.fetch("""SELECT s.name, s.role, l.t_in, l.t_out, l.status 
                                FROM logs l JOIN staff s ON l.staff_id = s.id 
                                WHERE l.date=?""", (self.filter_date,))
        
        present = sum(1 for x in logs if x[3] is None) # t_out is None
        late = sum(1 for x in logs if x[4] == "LATE")

        # Stats Row
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=(0,20))
        self._stat_card(row, "Present Now", str(present), Theme.SUCCESS)
        self._stat_card(row, "Late Arrivals", str(late), Theme.DANGER)
        self._stat_card(row, "Total Logs", str(len(logs)), Theme.ACCENT)

        # Table
        tbl_frame = ctk.CTkScrollableFrame(self.content, fg_color=Theme.CARD, corner_radius=15)
        tbl_frame.pack(fill="both", expand=True)
        
        # Headers
        h_frame = ctk.CTkFrame(tbl_frame, fg_color="transparent"); h_frame.pack(fill="x", pady=5)
        cols = ["Employee", "Role", "In Time", "Out Time", "Status"]
        for i, c in enumerate(cols): 
            ctk.CTkLabel(h_frame, text=c, font=("Inter", 12, "bold"), width=150, anchor="w", text_color=Theme.TEXT_DIM).grid(row=0, column=i, padx=10)
        
        ctk.CTkFrame(tbl_frame, height=1, fg_color=Theme.BORDER).pack(fill="x", pady=5)

        # Rows
        for entry in logs:
            r = ctk.CTkFrame(tbl_frame, fg_color="transparent", height=40); r.pack(fill="x", pady=2)
            for i, val in enumerate(entry):
                val = val if val else "--:--"
                col = Theme.TEXT if i==0 else Theme.TEXT_DIM
                if i == 4: col = Theme.SUCCESS if val=="ON TIME" else Theme.DANGER if val=="LATE" else Theme.TEXT_DIM # Status color
                
                ctk.CTkLabel(r, text=val, width=150, anchor="w", font=("Inter", 13), text_color=col).grid(row=0, column=i, padx=10)

    def _stat_card(self, parent, title, val, color):
        f = ctk.CTkFrame(parent, fg_color=Theme.CARD, height=100); f.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(f, text=title, text_color=Theme.TEXT_DIM, font=("Inter", 12)).pack(anchor="w", padx=20, pady=(20,0))
        ctk.CTkLabel(f, text=val, text_color=color, font=("Inter", 32, "bold")).pack(anchor="w", padx=20)

    # --- DASHBOARD: STAFF HUB ---
    def render_staff(self):
        for w in self.content.winfo_children(): w.destroy()
        
        # Top Bar
        top = ctk.CTkFrame(self.content, fg_color="transparent"); top.pack(fill="x", pady=(0,20))
        ctk.CTkLabel(top, text="Staff Management", font=("Inter", 24, "bold")).pack(side="left")
        
        # Edit/Add Form
        form = ctk.CTkFrame(self.content, fg_color=Theme.CARD, border_width=1, border_color=Theme.BORDER); form.pack(fill="x", pady=10, ipady=10)
        
        self.s_name = ctk.CTkEntry(form, placeholder_text="Full Name", width=200, fg_color=Theme.BG_MAIN, border_width=0)
        self.s_name.grid(row=0, column=0, padx=15, pady=15)
        
        self.s_pin = ctk.CTkEntry(form, placeholder_text="PIN (4)", width=80, fg_color=Theme.BG_MAIN, border_width=0)
        self.s_pin.grid(row=0, column=1, padx=5)
        
        self.s_time = ctk.CTkEntry(form, placeholder_text="09:00", width=80, fg_color=Theme.BG_MAIN, border_width=0)
        self.s_time.grid(row=0, column=2, padx=5)
        
        self.s_role = ctk.CTkOptionMenu(form, values=["Manager", "Staff", "Cashier", "Tech"], width=110, fg_color=Theme.BG_MAIN)
        self.s_role.grid(row=0, column=3, padx=5)
        
        self.s_type = ctk.CTkOptionMenu(form, values=["Full-Time", "Part-Time"], width=110, fg_color=Theme.BG_MAIN)
        self.s_type.grid(row=0, column=4, padx=5)
        
        # Dynamic Button
        btn_txt = "Update Staff" if self.edit_mode_id else "+ Add New"
        btn_col = "#d97706" if self.edit_mode_id else Theme.ACCENT
        ctk.CTkButton(form, text=btn_txt, fg_color=btn_col, width=100, command=self.save_staff).grid(row=0, column=5, padx=15)
        
        if self.edit_mode_id:
            ctk.CTkButton(form, text="Cancel", fg_color="transparent", width=60, command=self.cancel_edit).grid(row=0, column=6)

        # List
        lst = ctk.CTkScrollableFrame(self.content, fg_color="transparent"); lst.pack(fill="both", expand=True)
        
        staff = self.db.fetch("SELECT * FROM staff")
        for s in staff:
            # s = (id, name, pin, role, type, start)
            row = ctk.CTkFrame(lst, fg_color=Theme.CARD, height=60); row.pack(fill="x", pady=4)
            
            info = f"{s[1]}  |  {s[3]}  |  {s[5]} Start"
            ctk.CTkLabel(row, text=info, font=("Inter", 14, "bold"), text_color=Theme.TEXT).pack(side="left", padx=20)
            ctk.CTkLabel(row, text=f"PIN: {s[2]}", text_color=Theme.TEXT_DIM).pack(side="left", padx=10)
            
            ctk.CTkButton(row, text="DELETE", fg_color=Theme.DANGER, width=60, height=25, command=lambda x=s[0]: self.delete_staff(x)).pack(side="right", padx=15)
            ctk.CTkButton(row, text="EDIT", fg_color=Theme.BG_SIDE, width=60, height=25, border_width=1, border_color=Theme.BORDER, command=lambda x=s: self.load_edit(x)).pack(side="right", padx=5)

    def load_edit(self, data):
        self.edit_mode_id = data[0]
        self.s_name.delete(0,'end'); self.s_name.insert(0, data[1])
        self.s_pin.delete(0,'end'); self.s_pin.insert(0, data[2])
        self.s_role.set(data[3])
        self.s_type.set(data[4])
        self.s_time.delete(0,'end'); self.s_time.insert(0, data[5])
        self.render_staff()

    def cancel_edit(self):
        self.edit_mode_id = None
        self.render_staff()

    def save_staff(self):
        # Validation
        nm, pn, rl, tp, tm = self.s_name.get(), self.s_pin.get(), self.s_role.get(), self.s_type.get(), self.s_time.get()
        if not nm or len(pn) != 4:
            messagebox.showerror("Error", "Name required & PIN must be 4 digits.")
            return

        try:
            if self.edit_mode_id:
                self.db.commit("UPDATE staff SET name=?, pin=?, role=?, job_type=?, start_time=? WHERE id=?", (nm, pn, rl, tp, tm, self.edit_mode_id))
                self.edit_mode_id = None
            else:
                self.db.commit("INSERT INTO staff (name, pin, role, job_type, start_time) VALUES (?,?,?,?,?)", (nm, pn, rl, tp, tm))
            self.render_staff()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "PIN already in use.")

    def delete_staff(self, uid):
        if messagebox.askyesno("Delete", "Are you sure? This deletes all their logs too."):
            self.db.commit("DELETE FROM logs WHERE staff_id=?", (uid,)) # Double check cleanup
            self.db.commit("DELETE FROM staff WHERE id=?", (uid,))
            self.render_staff()

    # --- DASHBOARD: SETTINGS ---
    def render_settings(self):
        for w in self.content.winfo_children(): w.destroy()
        ctk.CTkLabel(self.content, text="Advanced Settings", font=("Inter", 24, "bold")).pack(anchor="w", pady=(0,20))

        # Admin Config
        sec = self._setting_group("Security Configuration")
        self.c_pin = self._setting_input(sec, "Admin PIN", "admin_pin")
        self.c_grace = self._setting_input(sec, "Late Grace Period (Mins)", "grace_period")
        ctk.CTkButton(sec, text="Save Config", fg_color=Theme.ACCENT, command=self.save_config).pack(anchor="w", padx=20, pady=20)

        # Database Tools
        data = self._setting_group("Database & Backup")
        ctk.CTkButton(data, text="💾 Backup Database", fg_color=Theme.BG_SIDE, border_width=1, border_color=Theme.BORDER, command=self.backup_db).pack(side="left", padx=20, pady=20)
        ctk.CTkButton(data, text="📊 Export Excel Report", fg_color=Theme.BG_SIDE, border_width=1, border_color=Theme.BORDER, command=self.export_excel).pack(side="left", padx=5)
        ctk.CTkButton(data, text="☢️ FACTORY RESET", fg_color=Theme.DANGER, command=self.factory_reset).pack(side="right", padx=20)

    def _setting_group(self, title):
        f = ctk.CTkFrame(self.content, fg_color=Theme.CARD, border_width=1, border_color=Theme.BORDER); f.pack(fill="x", pady=10)
        ctk.CTkLabel(f, text=title, font=("Inter", 14, "bold"), text_color=Theme.ACCENT).pack(anchor="w", padx=20, pady=15)
        return f

    def _setting_input(self, parent, label, db_key):
        ctk.CTkLabel(parent, text=label, text_color=Theme.TEXT_DIM).pack(anchor="w", padx=20, pady=(5,0))
        e = ctk.CTkEntry(parent, width=300, fg_color=Theme.BG_MAIN, border_width=0)
        e.pack(anchor="w", padx=20, pady=5)
        val = self.db.fetch("SELECT val FROM config WHERE key=?", (db_key,))
        if val: e.insert(0, val[0][0])
        return e

    def save_config(self):
        self.db.commit("UPDATE config SET val=? WHERE key='admin_pin'", (self.c_pin.get(),))
        self.db.commit("UPDATE config SET val=? WHERE key='grace_period'", (self.c_grace.get(),))
        messagebox.showinfo("Saved", "Configuration updated.")

    def backup_db(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", initialfile=f"Backup_{datetime.date.today()}.db")
        if path: shutil.copy(DB_FILE, path); messagebox.showinfo("Done", "Backup created successfully.")

    def export_excel(self):
        logs = self.db.fetch("""SELECT s.name, s.role, l.date, l.t_in, l.t_out, l.status 
                                FROM logs l JOIN staff s ON l.staff_id = s.id""")
        path = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if path:
            pd.DataFrame(logs, columns=["Name","Role","Date","In","Out","Status"]).to_excel(path, index=False)
            messagebox.showinfo("Done", "Excel file exported.")

    def factory_reset(self):
        if messagebox.askyesno("WARNING", "This will delete ALL data. Cannot be undone. Proceed?"):
            if ctk.CTkInputDialog(text="Type 'RESET' to confirm:", title="Confirm").get_input() == "RESET":
                self.db.commit("DELETE FROM logs"); self.db.commit("DELETE FROM staff")
                messagebox.showinfo("Reset", "System wiped clean.")
                self.show_login()

    # ==========================
    # 📟 3. TERMINAL MODE
    # ==========================
    def launch_terminal(self):
        self.clear(); self.view = "TERMINAL"
        
        # Full Screen
        term = ctk.CTkFrame(self, fg_color=Theme.BG_MAIN)
        term.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.active_frame = term

        # Header
        ctk.CTkButton(term, text="EXIT", width=80, fg_color=Theme.BG_SIDE, command=self.exit_terminal).place(x=30, y=30)
        
        # Center Content
        center = ctk.CTkFrame(term, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        self.clock = ctk.CTkLabel(center, text="00:00:00", font=("Inter", 100, "bold"), text_color=Theme.TEXT)
        self.clock.pack(pady=(0,20))
        
        self.status_msg = ctk.CTkLabel(center, text="READY TO SCAN", font=("Inter", 24), text_color=Theme.ACCENT)
        self.status_msg.pack(pady=(0,40))

        # PIN Indicators
        self.term_pin = ""
        dots_f = ctk.CTkFrame(center, fg_color="transparent"); dots_f.pack(pady=(0,30))
        self.dots = [ctk.CTkFrame(dots_f, width=20, height=20, corner_radius=10, fg_color=Theme.BG_SIDE) for _ in range(4)]
        for d in self.dots: d.pack(side="left", padx=8)

        # Numpad
        pad = ctk.CTkFrame(center, fg_color="transparent"); pad.pack()
        keys = ['1','2','3','4','5','6','7','8','9','CLR','0','➜']
        for i, k in enumerate(keys):
            cmd = lambda x=k: self._input_handler(x) if x != '➜' else None # Arrow is visual only in terminal
            color = Theme.BG_SIDE
            ctk.CTkButton(pad, text=k, width=90, height=90, corner_radius=45, fg_color=color, hover_color=Theme.BORDER,
                          text_color="white", font=("Inter", 24, "bold"), command=cmd).grid(row=i//3, column=i%3, padx=12, pady=12)

        self.update_clock()

    def update_clock(self):
        if self.view == "TERMINAL":
            self.clock.configure(text=datetime.datetime.now().strftime("%H:%M:%S"))
            self.after(1000, self.update_clock)

    def _update_term_display(self):
        # Update dots
        for i, d in enumerate(self.dots):
            d.configure(fg_color=Theme.ACCENT if i < len(self.term_pin) else Theme.BG_SIDE)
        
        # Check if full
        if len(self.term_pin) == 4:
            self.after(100, self.process_attendance)

    def process_attendance(self):
        pin = self.term_pin
        self.term_pin = ""
        self._update_term_display()
        
        # Verify User
        user = self.db.fetch("SELECT id, name, start_time FROM staff WHERE pin=?", (pin,))
        
        if not user:
            self.status_msg.configure(text="UNKNOWN PIN", text_color=Theme.DANGER)
            winsound.Beep(500, 300)
        else:
            uid, name, start = user[0]
            now = datetime.datetime.now()
            today = now.strftime("%Y-%m-%d")
            
            # Check for Open Shift
            active = self.db.fetch("SELECT id FROM logs WHERE staff_id=? AND date=? AND t_out IS NULL", (uid, today))
            
            if active:
                # Clock OUT
                self.db.commit("UPDATE logs SET t_out=? WHERE id=?", (now.strftime("%H:%M"), active[0][0]))
                self.status_msg.configure(text=f"GOODBYE, {name.upper()}", text_color=Theme.TEXT_DIM)
                winsound.Beep(800, 200)
            else:
                # Clock IN
                grace = int(self.db.fetch("SELECT val FROM config WHERE key='grace_period'")[0][0])
                # Handle missing or invalid start_time
                if not start or ':' not in str(start):
                    start = "09:00"  # Default start time
                try:
                    sh, sm = map(int, str(start).split(':'))
                    shift_start = now.replace(hour=sh, minute=sm, second=0)
                    is_late = now > (shift_start + datetime.timedelta(minutes=grace))
                    status = "LATE" if is_late else "ON TIME"
                except (ValueError, AttributeError):
                    # If parsing fails, default to ON TIME
                    status = "ON TIME"
                    is_late = False
                
                self.db.commit("INSERT INTO logs (staff_id, date, t_in, status) VALUES (?,?,?,?)", (uid, today, now.strftime("%H:%M"), status))
                col = Theme.DANGER if is_late else Theme.SUCCESS
                self.status_msg.configure(text=f"WELCOME, {name.upper()}", text_color=col)
                winsound.Beep(1000, 200)
        
        # Reset Status
        self.after(3000, lambda: self.status_msg.configure(text="READY TO SCAN", text_color=Theme.ACCENT))

    def exit_terminal(self):
        admin_pin = self.db.fetch("SELECT val FROM config WHERE key='admin_pin'")[0][0]
        if ctk.CTkInputDialog(text="Admin PIN:", title="Verify").get_input() == admin_pin:
            self.show_dashboard()

if __name__ == "__main__":
    App().mainloop()