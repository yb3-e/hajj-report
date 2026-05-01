from flask import Flask, render_template_string
import requests
import pandas as pd
import os
import gc
from datetime import datetime
import threading
import time

app = Flask(__name__)

# ==========================================
# ⚙️ إعدادات المسارات
# ==========================================
EXCEL_FILE_PATH = "staff_data.xlsx"
CACHE_FILE = "cached_report.html"

COL_NAMES_ID = ["رقم الهوية", "الهوية", "رقم الهويه"]
COL_NAMES_COMPANY = ["الشركة المشغلة", "الشركة"]
COL_NAMES_JOB = ["المهنة", "الوظيفة"]
COL_NAMES_SHIFT = ["الوردية", "الوقت"]
API_COL_ID = "nationalId" 
# ==========================================

is_updating = False 

def fetch_and_build_html():
    global is_updating
    if is_updating:
        return
    is_updating = True

    try:
        url = "https://tnql-prod.sejeltech.app/api/StaffMember/GetStaffMember"
        TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1laWQiOiIxNjQ5MSIsInVuaXF1ZV9uYW1lIjoi2LnYqNiv2KfZhNi52LLZitiyINi52KjYr9in2YTZhNmHINin2YTYtNmH2LHZiiIsImVtYWlsIjoiRTExMjY0MTU2MzUiLCJwcmltYXJ5Z3JvdXBzaWQiOiJFbXBsb3llZSIsIkFwcGxpY2F0aW9uIjoiUG9ydGFsIiwiRGV2aWNlU2VyaWFsIjoiIiwibmJmIjoxNzc3NjEyNTM4LCJleHAiOjE3Nzc2NTU3MzgsImlhdCI6MTc3NzYxMjUzOCwiaXNzIjoiVGFuYXFvbEFQSSIsImF1ZCI6IlRhbmFxb2xBUEkifQ.kllYcwHoTovb_nsqYEmgwiEi2fyR8qI8FV8pQh8yKlE"
        
        headers = {
            "accept": "application/json",
            "authorization": TOKEN,
            "content-type": "application/json",
            "lang": "ar"
        }
        
        lite_data = []
        page_size = 1500 # سحب البيانات على دفعات صغيرة لحماية السيرفر
        
        # 🔥 تكتيك التجزئة: حلقة تكرارية تسحب البيانات دفعة دفعة 🔥
        for page in range(1, 15): # نلف حتى 15 صفحة كحد أقصى (15*1500 = 22,500 موظف)
            payload = {
                "paging": {
                    "sortField": "Id", "searchOrder": 2, "pageIndex": page,
                    "pageSize": page_size, "sortBy": "Id Desc"
                },
                "data": {
                    "searchText": "", "name": "", "EmployeeId": None,
                    "OccupationIds": [], "DepartmentIds": [], "SectionIds": [],
                    "WorkShiftIds": [], "EmployeeTypes": [], "ManagerIds": [],
                    "OperatorCompanyIds": [], "NationalIdExpired": [],
                    "ActiveStatus": [True], "isPrinted": None, "isDeleted": False
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                break
                
            api_res = response.json()
            if not isinstance(api_res, dict): break
                
            res_data = api_res.get('data')
            if res_data is None: break

            all_employees = res_data if isinstance(res_data, list) else res_data.get('list', [])
            if not all_employees: 
                break # إذا مافي بيانات، يعني خلصنا كل الموظفين فنوقف الحلقة

            keys_to_keep = ['nationalId', 'operatorCompanyName', 'workShiftName', 'occupationName', 'employeeTypeName']
            for emp in all_employees:
                lite_data.append({k: emp.get(k) for k in keys_to_keep})
                
            # تنظيف الرام بعد كل صفحة
            del api_res, res_data, all_employees
            gc.collect()
            
            # حماية إضافية
            time.sleep(1) 

        if not lite_data:
            error_msg = f"<h1 dir='rtl' style='text-align:center; color:#c0392b; margin-top:100px;'>⚠️ لم يتم العثور على بيانات أو التوكن منتهي.</h1>"
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                f.write(error_msg)
            return

        df = pd.DataFrame(lite_data)
        del lite_data
        gc.collect()

        df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')

        if os.path.exists(EXCEL_FILE_PATH):
            try:
                df_excel = pd.read_excel(EXCEL_FILE_PATH)
                df[API_COL_ID] = df[API_COL_ID].astype(str).str.strip()
                id_col = next((c for c in COL_NAMES_ID if c in df_excel.columns), None)
                if id_col:
                    cols_to_keep = [id_col] + [c for c in (COL_NAMES_COMPANY + COL_NAMES_JOB + COL_NAMES_SHIFT) if c in df_excel.columns]
                    df_excel = df_excel[cols_to_keep].drop_duplicates(subset=[id_col])
                    df_excel[id_col] = df_excel[id_col].astype(str).str.strip()
                    df = pd.merge(df, df_excel, left_on=API_COL_ID, right_on=id_col, how='left')
                    del df_excel
                    gc.collect()
                    for api_c, ex_list in [('operatorCompanyName', COL_NAMES_COMPANY), ('occupationName', COL_NAMES_JOB), ('workShiftName', COL_NAMES_SHIFT)]:
                        ex_c = next((c for c in ex_list if c in df.columns), None)
                        if ex_c: df[api_c] = df[ex_c].fillna(df[api_c])
            except Exception as e:
                pass

        df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')

        total_employees = len(df)
        total_companies = df['operatorCompanyName'].nunique()
        total_shifts = df['workShiftName'].nunique()
        
        def clean_type(val):
            v = str(val).lower()
            if 'seasonal' in v or 'موسمي' in v: return 'موسمي'
            if 'permanent' in v or 'دائم' in v: return 'دائم'
            return 'غير محدد'
            
        df['mapped_type'] = df['employeeTypeName'].apply(clean_type)
        permanent_count = len(df[df['mapped_type'] == 'دائم'])
        seasonal_count = len(df[df['mapped_type'] == 'موسمي'])

        df_lite = df[['operatorCompanyName', 'workShiftName', 'occupationName']].copy()
        del df
        gc.collect()

        current_time = datetime.now().strftime("%I:%M %p")

        html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: #004d40; --secondary: #00796b; --accent: #c0a16b; --bg: #f4f7f6; }}
        body {{ font-family: 'Cairo', sans-serif; background-color: var(--bg); margin: 0; padding: 20px; color: #2c3e50; }}
        .header {{ text-align: center; background: linear-gradient(135deg, var(--primary), var(--secondary)); padding: 60px 20px; border-radius: 30px; color: white; box-shadow: 0 15px 35px rgba(0,0,0,0.2); position: relative; overflow: hidden; }}
        .eng-badge {{ position: relative; z-index: 2; display: inline-block; border: 2px solid var(--accent); padding: 12px 35px; border-radius: 15px; margin-bottom: 25px; background: rgba(0,0,0,0.3); }}
        .eng-badge .title {{ display: block; font-size: 1.2em; color: var(--accent); font-weight: 900; letter-spacing: 2px; }}
        .eng-badge .name {{ display: block; font-size: 1.8em; font-weight: 700; }}
        h1 {{ font-size: 2.8em; margin: 10px 0; position: relative; z-index: 2; text-shadow: 3px 3px 6px rgba(0,0,0,0.3); }}
        .live-indicator {{ background: rgba(255,255,255,0.15); padding: 8px 20px; border-radius: 50px; font-weight: 700; font-size: 0.9em; display: inline-flex; align-items: center; gap: 10px; margin-top: 15px; border: 1px solid rgba(255,255,255,0.3); }}
        .pulse {{ height: 12px; width: 12px; background-color: #4caf50; border-radius: 50%; display: inline-block; animation: pulse-animation 1.5s infinite; }}
        @keyframes pulse-animation {{ 0% {{ box-shadow: 0 0 0 0px rgba(76, 175, 80, 0.7); }} 100% {{ box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }} }}
        .stats-container {{ display: flex; gap: 15px; justify-content: center; margin: -40px 0 50px; position: relative; z-index: 3; flex-wrap: wrap; }}
        .stat-card {{ background: white; padding: 20px 15px; border-radius: 20px; text-align: center; min-width: 160px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); border-bottom: 6px solid var(--accent); flex: 1; max-width: 200px; }}
        .stat-card b {{ display: block; font-size: 2.5em; color: var(--primary); line-height: 1.1; margin-bottom: 5px; }}
        .stat-card span {{ font-size: 0.95em; font-weight: 700; color: #7f8c8d; }}
        .company-card {{ background: white; padding: 35px; border-radius: 30px; margin-bottom: 40px; box-shadow: 0 15px 40px rgba(0,0,0,0.05); }}
        .company-title {{ font-size: 2em; color: var(--primary); border-bottom: 3px solid #f0f0f0; padding-bottom: 20px; margin-bottom: 25px; font-weight: 900; }}
        .shift-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; }}
        .shift-box {{ background: #fafafa; border: 1px solid #eef2f3; padding: 25px; border-radius: 20px; }}
        .shift-name {{ color: var(--secondary); font-weight: 800; font-size: 1.3em; margin-bottom: 15px; display: block; border-right: 5px solid var(--accent); padding-right: 15px; }}
        .jobs-list {{ list-style: none; padding: 0; margin: 0; }}
        .jobs-list li {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #ddd; font-weight: 700; }}
        .job-val {{ background: var(--primary); color: white; padding: 3px 12px; border-radius: 8px; font-size: 0.9em; }}
        .grand-summary {{ background: #ffffff; border: 4px solid var(--primary); padding: 40px; border-radius: 40px; margin-top: 60px; }}
        .grand-summary h2 {{ text-align: center; color: var(--primary); font-size: 2.2em; margin-bottom: 35px; font-weight: 900; }}
        .grand-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .grand-item {{ background: #e0f2f1; padding: 15px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; font-weight: 800; border-right: 5px solid var(--primary); }}
        .footer {{ text-align: center; margin-top: 80px; padding: 50px; border-top: 2px solid #eee; color: #7f8c8d; }}
        .footer b {{ color: var(--primary); font-size: 1.5em; display: block; margin-top: 10px; font-family: 'Courier New', monospace; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="eng-badge" dir="ltr"><span class="title">Eng.</span><span class="name">Abdulaziz Alshehri</span></div>
        <h1>التقرير الشامل لموسم حج 1447</h1>
        <div class="live-indicator"><span class="pulse"></span>آخر تحديث للبيانات: {current_time}</div>
    </div>
    <div class="stats-container">
        <div class="stat-card"><b>{total_employees}</b><span>إجمالي الفعالين</span></div>
        <div class="stat-card"><b>{permanent_count}</b><span>موظفين دائمين</span></div>
        <div class="stat-card"><b>{seasonal_count}</b><span>موظفين موسميين</span></div>
        <div class="stat-card"><b>{total_companies}</b><span>الشركات المشغلة</span></div>
        <div class="stat-card"><b>{total_shifts}</b><span>إجمالي الورديات</span></div>
    </div>
    <div class="content">
        {''' '''.join([f'''<div class="company-card"><div class="company-title">🏢 {c}</div><div class="shift-grid">{" ".join([f'''<div class="shift-box"><span class="shift-name">📍 {s}</span><ul class="jobs-list">{" ".join([f'<li><span>{j}</span><span class="job-val">{v}</span></li>' for j, v in df_lite[(df_lite['operatorCompanyName']==c) & (df_lite['workShiftName']==s)]['occupationName'].value_counts().items()])}</ul></div>''' for s in df_lite[df_lite['operatorCompanyName']==c]['workShiftName'].unique()])}</div></div>''' for c in df_lite['operatorCompanyName'].unique()])}
    </div>
    <div class="grand-summary"><h2>📊 الملخص العام للوظائف (كافة الشركات)</h2><div class="grand-grid">{" ".join([f'<div class="grand-item"><span>{j}</span><span class="job-val">{v}</span></div>' for j, v in df_lite['occupationName'].value_counts().items()])}</div></div>
    <div class="footer" dir="ltr">PREPARED BY<br><b>Eng. Abdulaziz Alshehri</b></div>
</body></html>"""
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
            
    except Exception as e:
        error_msg = f"<h1 dir='rtl' style='text-align:center; color:#c0392b; margin-top:100px;'>⚠️ خطأ برمجي أثناء سحب البيانات:<br>{str(e)}</h1>"
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(error_msg)
    finally:
        is_updating = False

@app.route('/')
def index():
    need_update = True
    if os.path.exists(CACHE_FILE):
        file_age = time.time() - os.path.getmtime(CACHE_FILE)
        if file_age < 7200: 
            need_update = False
            
    if need_update:
        threading.Thread(target=fetch_and_build_html).start()
        # نكتب ملف مؤقت عشان نمنع السبام (F5) من تحميل السيرفر
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("""<div style="text-align:center; margin-top:100px; font-family:sans-serif; direction:rtl;"><h1 style="color:#004d40;">⚙️ جاري معالجة التقرير بدقة (نظام التجزئة يعمل)...</h1><p style="font-size:1.2em; color:#555;">الرجاء عدم تحديث الصفحة بشكل متكرر. انتظر دقيقة واحدة ثم حدث الصفحة.</p></div>""")
        
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return "جاري بدء النظام..."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
