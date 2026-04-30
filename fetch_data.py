try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            api_res = response.json()
            
            # --- التعديل الذكي لحماية الكود من الانهيار ---
            if not isinstance(api_res, dict):
                return None, "رد غير مفهوم من السيرفر."
                
            res_data = api_res.get('data')
            
            # إذا السيرفر رد بـ null (وهنا كانت المشكلة)
            if res_data is None:
                # نجيب رسالة الخطأ الأصلية من السيرفر عشان نعرف السبب
                server_msg = api_res.get('message', api_res.get('Message', 'السيرفر رفض الطلب ولم يرسل بيانات.'))
                return None, f"تنبيه من السيرفر: {server_msg}"
                
            all_employees = res_data if isinstance(res_data, list) else res_data.get('list', [])
            # ----------------------------------------------

            if not all_employees:
                return None, "لا توجد بيانات حالية في السيرفر"

            df = pd.DataFrame(all_employees)
            df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')

            # الربط مع ملف الإكسيل
            if os.path.exists(EXCEL_FILE_PATH):
                try:
                    df_excel = pd.read_excel(EXCEL_FILE_PATH)
                    df[API_COL_ID] = df[API_COL_ID].astype(str).str.strip()
                    id_col = next((c for c in COL_NAMES_ID if c in df_excel.columns), None)
                    if id_col:
                        df_excel[id_col] = df_excel[id_col].astype(str).str.strip()
                        excel_subset = df_excel.drop_duplicates(subset=[id_col])
                        df = pd.merge(df, excel_subset, left_on=API_COL_ID, right_on=id_col, how='left')
                        
                        for api_c, ex_list in [('operatorCompanyName', COL_NAMES_COMPANY), ('occupationName', COL_NAMES_JOB), ('workShiftName', COL_NAMES_SHIFT)]:
                            ex_c = next((c for c in ex_list if c in df_excel.columns), None)
                            if ex_c: df[api_c] = df[ex_c].fillna(df[api_c])
                except Exception as e:
                    print(f"Excel Error: {e}")

            df = df.fillna('غير محدد').replace(['null', 'None', 'nan', '', None], 'غير محدد')
            return df, None
    except Exception as e:
        return None, str(e)
    return None, f"فشل الاتصال، الكود: {response.status_code}"
