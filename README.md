# Tool.Eisenhower

Cấu trúc project (gợi ý)
Eisenhower-3x3/
├─ requirements.txt
├─ README.md
├─ .gitignore
└─ src/
   ├─ app.py
   ├─ models/
   │   └─ task.py
   ├─ ui/
   │   └─ main_window.py
   └─ db/
       └─ db.py

## Eisenhower-3x3 (prototype)

Quick start (Windows):

1. Tạo virtualenv:
    ```powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1   # powershell
    ```
2. Cài dependencies:
    ```powershell
        pip install --upgrade pip
        pip install -r requirements.txt
    ```
3. Chạy:
   ```powershell
        python src\app.py
    ```