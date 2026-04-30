from flask import Flask, render_template_string
import requests
import pandas as pd
import os
import re
from datetime import datetime

app = Flask(__name__)

# ==========================================
# ⚙️ إعدادات النظام (المسارات والمسميات)
# ==========================================
EXCEL_FILE_PATH = r"C:\Users\njm20\فريق العمل_Export_2026-04-29_06-27.xlsx"

# الربط الذكي مع أعمدة الإكسيل
COL_NAMES_ID = ["رقم الهوية", "الهوية", "رقم الهويه"]
COL_NAMES_COMPANY = ["الشركة المشغلة", "الشركة"]
COL_NAMES_JOB = ["المهنة", "الوظيفة"]
COL_NAMES_SHIFT = ["الوردية", "الوقت"]

API_COL_ID = "nationalId"

def get_live_data_and_process():
    url = "https://tnql-prod.sejeltech.app/api/StaffMember/GetStaffMember"
    
    # الهيدرز (مطابقة للـ Fetch الخاص بك لضمان الدخول)
    headers = {
        "accept": "application/json",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1laWQiOiIxNjQ5MSIsInVuaXF1ZV9uYW1lIjoi2LnYqNiv2KfZhNi52LLZitiyINi52KjYr9in2YTZhNmHINin2YTYtNmH2LHZiiIsImVtYWlsIjoiRTExMjY0MTU2MzUiLCJwcmltYXJ5Z3JvdXBzaWQiOiJFbXBsb3llZSIsIkFwcGxpY2F0aW9uIjoiUG9ydGFsIiwiRGV2aWNlU2VyaWFsIjoiIiwibmJmIjoxNzc3NTAxNzA2LCJleHAiOjE3Nzc1NDQ5MDYsImlhdCI6MTc3NzUwMTcwNiwiaXNzIjoiVGFuYXFvbEFQSSIsImF1ZCI6IlRhbmFxb2xBUEkifQ.MDWDyiZQj3xg4e_zDAtcPF9moWsOiAWD96_CJX8L71c",
        "content-type": "application/json",
        "lang": "ar",
        "referrer": "https://tnql-prod.sejeltech.app/human-resource/staff-list"
    }

    # الـ Payload المعتمد لجلب البيانات الفعالة
    payload = {
        "paging": {"sortField": "Id", "searchOrder": 2, "pageIndex": 1, "pageSize": 5000, "sortBy": "Id Desc"},
        "data": {"searchText": "", "ActiveStatus": [True], "isDeleted": False}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            api_res = response.json()
            res_data = api_res.get('data', [])
            all_employees = res_data if isinstance(res_data, list) else res_data.get('list', [])
            
            if not all_employees:
                return None, "لا توجد بيانات حالية في السيرفر"

            df = pd.DataFrame(all_employees)
            
            # 1. تنظيف أولي للـ null
            df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')

            # 2. الربط مع الإكسيل لتصحيح المسميات العربية
            if os.path.exists(EXCEL_FILE_PATH):
                df_excel = pd.read_excel(EXCEL_FILE_PATH)
                df[API_COL_ID] = df[API_COL_ID].astype(str).str.strip()
                
                # البحث عن عمود الهوية في الإكسيل
                id_col_excel = next((c for c in COL_NAMES_ID if c in df_excel.columns), None)
                
                if id_col_excel:
                    df_excel[id_col_excel] = df_excel[id_col_excel].astype(str).str.strip()
                    df = pd.merge(df, df_excel.drop_duplicates(subset=[id_col_excel]), left_on=API_COL_ID, right_on=id_col_excel, how='left')
                    
                    # استبدال أعمدة السيرفر بأعمدة الإكسيل العربية
                    mappings = [('operatorCompanyName', COL_NAMES_COMPANY), ('occupationName', COL_NAMES_JOB), ('workShiftName', COL_NAMES_SHIFT)]
                    for api_c, ex_list in mappings:
                        ex_c = next((c for c in ex_list if c in df_excel.columns), None)
                        if ex_c: df[api_c] = df[ex_c].fillna(df[api_c])
            
            # 3. تنظيف نهائي بعد الدمج
            df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')
            return df, None
            
    except Exception as e:
        return None, str(e)
    return None, "فشل الاتصال بالسيرفر"

@app.route('/')
def index():
    df, error = get_live_data_and_process()
    current_time = datetime.now().strftime("%I:%M:%S %p")
    
    if error:
        return f"<h1 style='text-align:center; margin-top:50px; color:red;'>⚠️ خطأ: {error}</h1>"

    # --- حساب الإحصائيات الفورية ---
    total_active = len(df)
    total_companies = df['operatorCompanyName'].nunique()
    
    # تصنيف دائم وموسمي
    def map_emp_type(val):
        v = str(val).lower()
        if 'seasonal' in v or 'موسمي' in v: return 'موسمي'
        if 'permanent' in v or 'دائم' in v: return 'دائم'
        return 'غير محدد'
    
    df['mapped_type'] = df['employeeTypeName'].apply(map_emp_type)
    perm_count = len(df[df['mapped_type'] == 'دائم'])
    seas_count = len(df[df['mapped_type'] == 'موسمي'])

    # --- بناء القالب الجمالي الموحد ---
    html_template = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>التقرير اللحظي - حج 1447</title>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            :root {{ --primary: #004d40; --secondary: #00796b; --accent: #c0a16b; --bg: #f4f7f6; }}
            body {{ font-family: 'Cairo', sans-serif; background-color: var(--bg); margin: 0; padding: 20px; color: #2c3e50; }}
            
            .header {{ text-align: center; background: linear-gradient(135deg, var(--primary), var(--secondary)); padding: 60px 20px; border-radius: 35px; color: white; box-shadow: 0 15px 35px rgba(0,0,0,0.2); position: relative; overflow: hidden; }}
            
            .eng-badge {{ position: relative; z-index: 2; display: inline-block; border: 2px solid var(--accent); padding: 12px 35px; border-radius: 15px; margin-bottom: 25px; background: rgba(0,0,0,0.3); }}
            .eng-badge .title {{ display: block; font-size: 1.2em; color: var(--accent); font-weight: 900; letter-spacing: 2px; }}
            .eng-badge .name {{ display: block; font-size: 1.8em; font-weight: 700; }}
            
            h1 {{ font-size: 2.8em; margin: 10px 0; text-shadow: 3px 3px 6px rgba(0,0,0,0.3); }}
            
            .live-indicator {{ background: rgba(255,255,255,0.15); padding: 8px 20px; border-radius: 50px; font-weight: 700; font-size: 0.9em; display: inline-flex; align-items: center; gap: 10px; margin-top: 15px; border: 1px solid rgba(255,255,255,0.3); }}
            .pulse {{ height: 12px; width: 12px; background-color: #4caf50; border-radius: 50%; display: inline-block; animation: pulse-animation 1.5s infinite; }}
            @keyframes pulse-animation {{ 0% {{ box-shadow: 0 0 0 0px rgba(76, 175, 80, 0.7); }} 100% {{ box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }} }}

            .stats-container {{ display: flex; gap: 15px; justify-content: center; margin: -40px 0 50px; position: relative; z-index: 3; flex-wrap: wrap; }}
            .stat-card {{ background: white; padding: 25px; border-radius: 20px; text-align: center; min-width: 170px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border-bottom: 6px solid var(--accent); flex: 1; max-width: 220px; }}
            .stat-card b {{ display: block; font-size: 2.8em; color: var(--primary); line-height: 1; margin-bottom: 8px; }}
            .stat-card span {{ font-size: 1em; font-weight: 800; color: #7f8c8d; }}

            .company-card {{ background: white; padding: 35px; border-radius: 30px; margin-bottom: 40px; box-shadow: 0 15px 40px rgba(0,0,0,0.05); }}
            .company-title {{ font-size: 2.1em; color: var(--primary); border-bottom: 3px solid #f0f0f0; padding-bottom: 20px; margin-bottom: 25px; font-weight: 900; display: flex; align-items: center; gap: 15px; }}
            
            .shift-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; }}
            .shift-box {{ background: #fafafa; border: 1px solid #eef2f3; padding: 25px; border-radius: 20px; transition: transform 0.3s; }}
            .shift-box:hover {{ transform: translateY(-5px); }}
            .shift-name {{ color: var(--secondary); font-weight: 800; font-size: 1.4em; margin-bottom: 15px; display: block; border-right: 6px solid var(--accent); padding-right: 15px; }}
            
            .jobs-list {{ list-style: none; padding: 0; margin: 0; }}
            .jobs-list li {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px dashed #ddd; font-weight: 700; font-size: 1.1em; }}
            .job-val {{ background: var(--primary); color: white; padding: 3px 15px; border-radius: 10px; font-size: 0.9em; }}

            .grand-summary {{ background: #ffffff; border: 4px solid var(--primary); padding: 45px; border-radius: 40px; margin-top: 60px; box-shadow: 0 20px 50px rgba(0,0,0,0.1); }}
            .grand-summary h2 {{ text-align: center; color: var(--primary); font-size: 2.4em; margin-bottom: 40px; font-weight: 900; }}
            .grand-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; }}
            .grand-item {{ background: #e0f2f1; padding: 20px; border-radius: 15px; display: flex; justify-content: space-between; align-items: center; font-weight: 800; border-right: 6px solid var(--primary); font-size: 1.1em; }}

            .footer {{ text-align: center; margin-top: 80px; padding: 60px; border-top: 2px solid #eee; color: #7f8c8d; }}
            .footer .eng-sig {{ display: block; margin-top: 15px; color: var(--primary); font-size: 1.6em; font-weight: 900; letter-spacing: 1px; font-family: 'Courier New', monospace; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="eng-badge" dir="ltr">
                <span class="title">Eng.</span>
                <span class="name">Abdulaziz Alshehri</span>
            </div>
            <h1>تقرير القوى العاملة - موسم حج 1447</h1>
            <div class="live-indicator">
                <span class="pulse"></span>
                تم تحديث الأرقام الآن: {current_time}
            </div>
        </div>

        <div class="stats-container">
            <div class="stat-card"><b>{total_active}</b><span>إجمالي الفعالين</span></div>
            <div class="stat-card"><b>{perm_count}</b><span>موظفين دائمين</span></div>
            <div class="stat-card"><b>{seas_count}</b><span>موظفين موسميين</span></div>
            <div class="stat-card"><b>{total_companies}</b><span>الشركات المشغلة</span></div>
        </div>

        <div class="content">
            {''' '''.join([f'''
            <div class="company-card">
                <div class="company-title">🏢 {c}</div>
                <div class="shift-grid">
                    {" ".join([f'''
                    <div class="shift-box">
                        <span class="shift-name">📍 {s}</span>
                        <ul class="jobs-list">
                            {" ".join([f'<li><span>{j}</span><span class="job-val">{v}</span></li>' 
                            for j, v in df[(df['operatorCompanyName']==c) & (df['workShiftName']==s)]['occupationName'].value_counts().items()])}
                        </ul>
                    </div>''' for s in df[df['operatorCompanyName']==c]['workShiftName'].unique()])}
                </div>
            </div>''' for c in df['operatorCompanyName'].unique()])}
        </div>

        <div class="grand-summary">
            <h2>📊 الملخص الشامل لكافة قطاعات الحج</h2>
            <div class="grand-grid">
                {" ".join([f'<div class="grand-item"><span>{j}</span><span class="job-val">{v}</span></div>' 
                for j, v in df['occupationName'].value_counts().items()])}
            </div>
        </div>

        <div class="footer" dir="ltr">
            PREPARED BY<br>
            <span class="eng-sig">Eng. Abdulaziz Alshehri</span>
            <br>Software Engineering @ UQU
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template)

if __name__ == '__main__':
    # يعمل على جميع الأجهزة في نفس الشبكة على بورت 5000
    app.run(host='0.0.0.0', port=5000, debug=False)