import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from flask import Flask, request, jsonify
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import threading
import requests
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Image
from reportlab.lib import colors
import bcrypt
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
# Databaze izveide
def init_db():
    conn = sqlite3.connect("budget.db")
    c = conn.cursor()
 

    c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL CHECK(length(password) >= 60))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                description TEXT,
                date TEXT NOT NULL DEFAULT (DATE('now')), 
                FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    c.execute("PRAGMA table_info(transactions)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'date' not in columns:
  
        c.execute('''CREATE TABLE new_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    amount REAL,
                    description TEXT,
                    date TEXT NOT NULL DEFAULT (DATE('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        c.execute('''INSERT INTO new_transactions 
                    (id, user_id, type, amount, description, date)
                    SELECT id, user_id, type, amount, description, DATE('now')
                    FROM transactions''')
        
        
        c.execute("DROP TABLE transactions")
        
        c.execute("ALTER TABLE new_transactions RENAME TO transactions")
    
    c.execute('''CREATE TABLE IF NOT EXISTS budget_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                month_year TEXT,
                limit_amount REAL,
                FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

init_db()

# Flask API
app = Flask(__name__)

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    conn = sqlite3.connect("budget.db")
    c = conn.cursor()
    c.execute("SELECT type, amount, description, date FROM transactions WHERE user_id = ?", (user_id,))
    data = c.fetchall()
    conn.close()
    return jsonify(data)

@app.route("/api/summary", methods=["GET"])
def get_summary():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    
    conn = sqlite3.connect("budget.db")
    c = conn.cursor()
    
    current_month = datetime.now().strftime("%Y-%m")
    c.execute('''SELECT limit_amount FROM budget_limits 
               WHERE user_id = ? AND month_year = ?''', (user_id, current_month))
    budget_limit = c.fetchone()
    budget_limit = budget_limit[0] if budget_limit else 0
    
    c.execute('''SELECT strftime('%Y-%m', date) as month,
               SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
               SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
               FROM transactions WHERE user_id = ?
               GROUP BY month ORDER BY month''', (user_id,))
    monthly_data = c.fetchall()
    
    c.execute('''SELECT SUM(amount) FROM transactions 
               WHERE user_id = ? AND type='income' 
               AND strftime('%Y-%m', date) = ?''', (user_id, current_month))
    total_income = c.fetchone()[0] or 0
    
    c.execute('''SELECT SUM(amount) FROM transactions 
               WHERE user_id = ? AND type='expense' 
               AND strftime('%Y-%m', date) = ?''', (user_id, current_month))
    total_expense = c.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        "total_income": total_income,
        "total_expense": total_expense,
        "monthly_data": monthly_data,
        "budget_limit": budget_limit
    })

# GUI 
class BudgetApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Budžeta pārvaldības sistēma")
        self.root.geometry("1000x800")
        self.root.configure(bg='#f0f0f0')
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Arial', 12), padding=5)
        self.style.configure('Treeview', rowheight=30)
        self.style.map('Treeview', background=[('selected', '#007bff')])
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.create_login_widgets()

    def create_login_widgets(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        login_frame = tk.Frame(self.root, bg='#f0f0f0')
        login_frame.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)
        
        tk.Label(login_frame, text="Budžeta apskats", font=('Arial', 24, 'bold'), 
                bg='#f0f0f0', fg='#333').pack(pady=20)
        
        form_frame = tk.Frame(login_frame, bg='#f0f0f0')
        form_frame.pack(pady=20)
        
        tk.Label(form_frame, text="Lietotājvārds", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=0, padx=10, pady=5)
        tk.Entry(form_frame, textvariable=self.username_var, font=('Arial', 12), 
                width=25).grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(form_frame, text="Pārole", font=('Arial', 12), bg='#f0f0f0').grid(row=1, column=0, padx=10, pady=5)
        tk.Entry(form_frame, textvariable=self.password_var, show="*", 
                font=('Arial', 12), width=25).grid(row=1, column=1, padx=10, pady=5)
        
        btn_frame = tk.Frame(login_frame, bg='#f0f0f0')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Reģistrācija", command=self.register, 
                 font=('Arial', 12), bg='#007bff', fg='white', width=12).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Ienākt", command=self.login, 
                 font=('Arial', 12), bg='#28a745', fg='white', width=12).pack(side=tk.LEFT, padx=10)

    def register(self):
        username = self.username_var.get().strip()  
        password = self.password_var.get().strip()
        

        if not username or not password:
            messagebox.showerror("Kļūda", "Lietotājvārds un parole nedrīkst būt tukši!")
            return
            
        if len(username) < 3:
            messagebox.showerror("Kļūda", "Lietotājvārdam jābūt vismaz 3 simbolus garam!")
            return
            
        if len(password) < 6:
            messagebox.showerror("Kļūda", "Parolei jābūt vismaz 6 simbolus garai!")
            return
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password.decode('utf-8')))
            conn.commit()
            messagebox.showinfo("Veiksmīgi", "Reģistrācija veiksmīga!")
        except sqlite3.IntegrityError:
            messagebox.showerror("Kļūda", "Lietotājvārds jau eksistē!")
        finally:
            conn.close()
    
    def login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            messagebox.showerror("Kļūda", "Lūdzu aizpildiet abus laukus!")
            return

        try:
            conn = sqlite3.connect("budget.db")
            c = conn.cursor()
            c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            conn.close()

            if user:
               
                stored_hash = user[1].encode('utf-8') 
                
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    self.user_id = user[0]
                    self.open_budget_window()
                else:
                    messagebox.showerror("Kļūda", "Nepareiza parole!")
            else:
                messagebox.showerror("Kļūda", "Lietotājs neeksistē!")

        except sqlite3.Error as e:
            messagebox.showerror("Datubāzes kļūda", f"Tehniskā kļūda: {str(e)}")
        except Exception as e:
            messagebox.showerror("Kritiskā kļūda", f"Negaidīta kļūda: {str(e)}")
    
    def open_budget_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        input_frame = tk.Frame(main_frame, bg='#f0f0f0')
        input_frame.pack(fill=tk.X, pady=10)
        
        self.amount_var = tk.DoubleVar()
        self.desc_var = tk.StringVar()
        
        tk.Label(input_frame, text="Summa(€) ", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=0, padx=5)
        tk.Entry(input_frame, textvariable=self.amount_var, font=('Arial', 12), width=15).grid(row=0, column=1, padx=5)
        
        tk.Label(input_frame, text="Apraksts", font=('Arial', 12), bg='#f0f0f0').grid(row=0, column=2, padx=5)
        tk.Entry(input_frame, textvariable=self.desc_var, font=('Arial', 12), width=30).grid(row=0, column=3, padx=5)
        
        btn_frame = tk.Frame(input_frame, bg='#f0f0f0')
        btn_frame.grid(row=0, column=4, padx=10)
        
        tk.Button(btn_frame, text="Pievienot ienākumu", command=lambda: self.add_transaction("income"),
                 bg='#28a745', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Pievienot izdevumu", command=lambda: self.add_transaction("expense"),
                 bg='#dc3545', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        
        tree_frame = tk.Frame(main_frame, bg='#f0f0f0')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.transactions_tree = ttk.Treeview(tree_frame, columns=("Type", "Amount", "Description", "Date"), show="headings")
        self.transactions_tree.heading("Type", text="Tips ↓", command=lambda: self.sort_treeview("Type", False))
        self.transactions_tree.heading("Amount", text="Summa ↓", command=lambda: self.sort_treeview("Amount", False))
        self.transactions_tree.heading("Description", text="Apraksts ↓", command=lambda: self.sort_treeview("Description", False))
        self.transactions_tree.heading("Date", text="Datums ↓", command=lambda: self.sort_treeview("Date", False))
        self.transactions_tree.column("Type", width=100, anchor=tk.CENTER)
        self.transactions_tree.column("Amount", width=150, anchor=tk.CENTER)
        self.transactions_tree.column("Description", width=300, anchor=tk.W)
        self.transactions_tree.column("Date", width=150, anchor=tk.CENTER)
        self.transactions_tree.tag_configure('income', background='#d4edda')
        self.transactions_tree.tag_configure('expense', background='#f8d7da')
        self.transactions_tree.pack(fill=tk.BOTH, expand=True)
        
        # Budget Limit Section
        limit_frame = tk.Frame(main_frame, bg='#f0f0f0')
        limit_frame.pack(pady=10, fill=tk.X)
        
        self.budget_limit_var = tk.DoubleVar()
        tk.Label(limit_frame, text="Menēša budžeta līmits:", 
                font=('Arial', 12), bg='#f0f0f0').pack(side=tk.LEFT)
        tk.Entry(limit_frame, textvariable=self.budget_limit_var, 
                font=('Arial', 12), width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(limit_frame, text="Pievienot līmitu", command=self.set_budget_limit,
                 font=('Arial', 12), bg='#007bff', fg='white').pack(side=tk.LEFT)
        
      
        summary_frame = tk.Frame(main_frame, bg='#ffffff', bd=1, relief=tk.SOLID)
        summary_frame.pack(fill=tk.X, pady=20, padx=10)
        
        tk.Label(summary_frame, text="Kopā ienākumi:", font=('Arial', 12), 
                bg='#ffffff').grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.total_income_label = tk.Label(summary_frame, text="$0.00", font=('Arial', 12), bg='#ffffff')
        self.total_income_label.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        tk.Label(summary_frame, text=" Kopā izdevumi:", font=('Arial', 12), 
                bg='#ffffff').grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        self.total_expense_label = tk.Label(summary_frame, text="$0.00", font=('Arial', 12), bg='#ffffff')
        self.total_expense_label.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        tk.Label(summary_frame, text="Balance:", font=('Arial', 12, 'bold'), 
                bg='#ffffff').grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        self.balance_label = tk.Label(summary_frame, text="$0.00", font=('Arial', 12, 'bold'), bg='#ffffff')
        self.balance_label.grid(row=2, column=1, padx=10, pady=5, sticky=tk.W)
        
        self.budget_limit_info = tk.Label(summary_frame, text="", font=('Arial', 12), bg='#ffffff')
        self.budget_limit_info.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        

        control_frame = tk.Frame(main_frame, bg='#f0f0f0')
        control_frame.pack(pady=10)
        
        tk.Button(control_frame, text="Paskatīt budžetu analīze", command=self.show_analysis,
                 font=('Arial', 12), bg='#17a2b8', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Eksportēt Excel", command=self.export_excel,
                 font=('Arial', 12), bg='#28a745', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Eksportēt PDF", command=self.export_pdf,
                 font=('Arial', 12), bg='#dc3545', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Iziet", command=self.logout, 
                 font=('Arial', 12), bg='#6c757d', fg='white').pack(side=tk.LEFT, padx=5)
        
        self.load_transactions()
        self.load_budget_limit()

    def add_transaction(self, trans_type):
        amount = self.amount_var.get()
        description = self.desc_var.get()
        current_date = datetime.now().strftime("%Y-%m-%d")  # Pievienojam pašreizējo datumu
    
        if amount <= 0 or not description:
            messagebox.showerror("Error", "Please enter valid amount and description")
            return
    
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        c.execute('''INSERT INTO transactions 
                (user_id, type, amount, description, date)
                VALUES (?, ?, ?, ?, ?)''', 
                (self.user_id, trans_type, amount, description, current_date))  # Eksplicīti norādām datumu
        conn.commit()
        conn.close()
      
        self.amount_var.set(0)
        self.desc_var.set("")
        self.load_transactions()
    
    def load_transactions(self):
        for row in self.transactions_tree.get_children():
            self.transactions_tree.delete(row)
        
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        c.execute("SELECT type, amount, description, date FROM transactions WHERE user_id = ?", (self.user_id,))
        transactions = c.fetchall()
        
        total_income = 0
        total_expense = 0
        for trans in transactions:
            if trans[0] == 'income':
                total_income += trans[1]
                self.transactions_tree.insert("", "end", values=trans, tags=('income',))
            else:
                total_expense += trans[1]
                self.transactions_tree.insert("", "end", values=trans, tags=('expense',))
        
        balance = total_income - total_expense
        self.total_income_label.config(text=f"${total_income:.2f}")
        self.total_expense_label.config(text=f"${total_expense:.2f}")
        self.balance_label.config(text=f"${balance:.2f}")
        self.balance_label.config(fg='#28a745' if balance >= 0 else '#dc3545')
        
        # Check budget limit
        current_month = datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        c.execute('''SELECT limit_amount FROM budget_limits 
                   WHERE user_id = ? AND month_year = ?''', 
                   (self.user_id, current_month))
        limit = c.fetchone()
        conn.close()
        
        if limit:
            limit = limit[0]
            remaining = limit - total_expense
            status = f"Mēnēša budžets: ${limit:.2f} | Status: ${remaining:.2f}"
            color = '#28a745' if remaining >= 0 else '#dc3545'
            self.budget_limit_info.config(text=status, fg=color)
    
    def sort_treeview(self, col, reverse):
        l = [(self.transactions_tree.set(k, col), k) for k in self.transactions_tree.get_children('')]
        
        try:
            if col == "Amount":
                l.sort(key=lambda t: float(t[0]), reverse=reverse)
            elif col == "Date":
                l.sort(key=lambda t: datetime.strptime(t[0], "%Y-%m-%d"), reverse=reverse)
            else:
                l.sort(reverse=reverse)
        except:
            pass
        
        for index, (val, k) in enumerate(l):
            self.transactions_tree.move(k, '', index)
            
        self.transactions_tree.heading(col, 
            text=f"{col} {'↑' if reverse else '↓'}",
            command=lambda: self.sort_treeview(col, not reverse))

    def show_analysis(self):
        analysis_win = tk.Toplevel(self.root)
        analysis_win.title("Budžeta analīze")
        analysis_win.geometry("1200x800")
        
        try:
            response = requests.get(f"http://localhost:5000/api/summary?user_id={self.user_id}")
            data = response.json()
        except Exception as e:
            messagebox.showerror("Error", f"Kļūda : {str(e)}")
            return
        
        fig = plt.Figure(figsize=(12, 8), dpi=100)
        fig.suptitle("Finanšu analīze", fontsize=16)
        
       
        ax1 = fig.add_subplot(221)
        ax1.set_title("Ienākumi un Izdevumi")
        labels = ['Ienākumi', 'Izdevumi']
        sizes = [data['total_income'], data['total_expense']]
        ax1.pie(sizes, labels=labels, autopct='%1.1f%%', colors=['#28a745', '#dc3545'])
        
   
        ax2 = fig.add_subplot(222)
        ax2.set_title("Pedēji  transakcijas")
        transactions = data['monthly_data'][-5:][::-1]
        amounts = [t[2] for t in transactions]
        labels = [t[0] for t in transactions]
        ax2.bar(labels, amounts, color='#007bff')
        ax2.tick_params(axis='x', rotation=45)
        
    
        ax3 = fig.add_subplot(212)
        ax3.set_title("Menēša tendences")	
        months = [t[0] for t in data['monthly_data']]
        income = [t[1] for t in data['monthly_data']]
        expenses = [t[2] for t in data['monthly_data']]
        ax3.plot(months, income, label='Income', color='#28a745', marker='o')
        ax3.plot(months, expenses, label='Expenses', color='#dc3545', marker='o')
        ax3.fill_between(months, income, expenses, color='#ffc107', alpha=0.3)
        ax3.legend()
        ax3.tick_params(axis='x', rotation=45)
        
        canvas = FigureCanvasTkAgg(fig, master=analysis_win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def set_budget_limit(self):
        limit = self.budget_limit_var.get()
        if limit <= 0:
            messagebox.showerror("Error", "Kļūda: Lūdzu ievadiet derīgu budžeta limitu!")
            return
        
        current_month = datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        try:
      
            c.execute('''SELECT id FROM budget_limits 
                    WHERE user_id = ? AND month_year = ?''', 
                    (self.user_id, current_month))
            existing_limit = c.fetchone()
            
            if existing_limit:
                
                c.execute('''UPDATE budget_limits 
                        SET limit_amount = ?
                        WHERE id = ?''', 
                        (limit, existing_limit[0]))
            else:
              
                c.execute('''INSERT INTO budget_limits 
                        (user_id, month_year, limit_amount) 
                        VALUES (?, ?, ?)''', 
                        (self.user_id, current_month, limit))
            
            conn.commit()
            messagebox.showinfo("Success", "Budžeta limits ir nomainīts!")
            self.load_transactions()  
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            conn.close()
    
    def load_budget_limit(self):
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        current_month = datetime.now().strftime("%Y-%m")
        c.execute('''SELECT limit_amount FROM budget_limits 
                   WHERE user_id = ? AND month_year = ?''', 
                   (self.user_id, current_month))
        limit = c.fetchone()
        self.budget_limit_var.set(limit[0] if limit else 0)
        conn.close()

    def export_excel(self):
       
        try:
            conn = sqlite3.connect("budget.db")
            query = '''SELECT date, type, amount, description 
                    FROM transactions 
                    WHERE user_id = ?'''
            df = pd.read_sql(query, conn, params=(self.user_id,))
            conn.close()

            if df.empty:
                messagebox.showwarning("Brīdinājums", "Nav datu eksportēšanai!")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Saglabāt kā Excel failu"
            )

            if file_path:
               
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                df['amount'] = df['amount'].apply(lambda x: f"€{x:.2f}")
                
                
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Transakcijas')
                    
                    
                    worksheet = writer.sheets['Transakcijas']
                    for col in worksheet.columns:
                        max_length = max(len(str(cell.value)) for cell in col)
                        worksheet.column_dimensions[col[0].column_letter].width = max_length + 2

                messagebox.showinfo("Success", f"Dati eksportēti:\n{file_path}")
                
        except PermissionError:
            messagebox.showerror("Error", "Nav piekļuves tiesību faila rakstīšanai!")
        except Exception as e:
            messagebox.showerror("Error", f"Eksportēšanas kļūda:\n{str(e)}")
    def export_pdf(self):
        conn = sqlite3.connect("budget.db")
        c = conn.cursor()
        c.execute('''SELECT date, type, amount, description 
                FROM transactions WHERE user_id = ?''', (self.user_id,))
        transactions = [("Date", "Type", "Amount", "Description")] + c.fetchall()
        
        c.execute('''SELECT strftime('%Y-%m', date) as month,
                SUM(CASE WHEN type='income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expense
                FROM transactions WHERE user_id = ?
                GROUP BY month ORDER BY month''', (self.user_id,))
        monthly_data = [("Month", "Income", "Expense")] + c.fetchall()
        conn.close()
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not file_path:
            return
        pdfmetrics.registerFont(TTFont("Arial", "arial.ttf"))
  
        fig = plt.Figure(figsize=(8, 6))
        ax = fig.add_subplot(111)
        ax.pie([self.total_income_label.cget("text")[1:], self.total_expense_label.cget("text")[1:]], 
            labels=['Ienākumi', 'Izdevumi'], autopct='%1.1f%%', colors=['#28a745', '#dc3545'])
        ax.set_title("Ienākumi un Izdevumi")
        
      
        from io import BytesIO
        chart_buffer = BytesIO()
        fig.savefig(chart_buffer, format='png')
        chart_buffer.seek(0)  
        

        pdf = canvas.Canvas(file_path, pagesize=letter)
        width, height = letter
        

        pdf.setFont("Arial", 16)
        pdf.drawString(72, height - 72, "Budžeta pārskats")
        
   
        pdf.setFont("Arial", 12)
        data = [["Datums", "Tips", "Summa", "Apraksts"]]
        for row in transactions[1:]:
            data.append([str(row[0]), row[1], f"${row[2]:.2f}", row[3]])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Arial'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.grey)
        ]))
        table.wrapOn(pdf, width-144, height)
        table.drawOn(pdf, 72, height - 200)
        

        from reportlab.lib.utils import ImageReader
        chart_image = ImageReader(chart_buffer)
        pdf.drawImage(chart_image, 72, height - 500, width=400, height=300)
        
  
        pdf.setFont("Arial", 14)
        pdf.drawString(72, height - 550, "Finanšu analīze:")
        pdf.setFont("Arial", 12)
        pdf.drawString(72, height - 570, f"Ienākumu summa: {self.total_income_label.cget('text')}")
        pdf.drawString(72, height - 590, f"Izdevumu summa: {self.total_expense_label.cget('text')}")
        pdf.drawString(72, height - 610, f"Atlikums: {self.balance_label.cget('text')}")
        
        pdf.save()
        messagebox.showinfo("Success", "PDF ir veiksmīgi ģenerēts!")

    def logout(self):
        self.user_id = None
        self.create_login_widgets()

def run_flask():
    app.run(threaded=True, use_reloader=False)  

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    root = tk.Tk()
    app = BudgetApp(root)
    root.mainloop()