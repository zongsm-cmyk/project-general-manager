# Project General Manager (مركز القيادة الموحد لإدارة المشاريع)

نظام تنسيق محلي مستقل لإدارة وتوجيه المشاريع المتعددة للمالك (`GitHub / First Dollar Engine`، `Gumroad`، `OpenSource Workflow`، `Etsy`)، مع الحفاظ الصارم على فصل السياقات، وتوثيق إيصالات التنفيذ في SQLite، وتكلفة تشغيلية صفرية تماماً (\$0).

---

## 1. بنية المنظومة (Architecture)

1. **خادم التنسيق المحلي (`orchestrator.py`):**
   - يعمل على المضيف المحلي `ws://127.0.0.1:8799`.
   - محمي بنظام أمان أصل الاتصال (`Origin Security`) لرفض أي طلبات خارجية (رمز الخطأ 1008).
   - يسجل كافة الإيصالات في قاعدة بيانات SQLite محلية (`receipts.db`).
   - يدير طابور الأوامر، ويمنع تكرار المعرفات (`Command ID Deduplication`)، ويمنع حلقات التوجيه (`Loop Guard`).
   - يستعيد المهام العالقة تلقائياً عند إعادة التشغيل (`Task Recovery`).

2. **المنسّق المحلي للمشاريع (`local_adapter.py`):**
   - يربط المدير العام مباشرة بمساحات العمل الحقيقية لمشاريع المالك:
     - `FirstDollarEngine` في `C:\Users\askgs\Documents\FirstDollarEngine`
     - `GUMROAD_CLI` في `C:\Users\askgs\Documents\GUMROAD_CLI`
     - `OpenSource_Workflow` في `C:\Users\askgs\Documents\OpenSource_Workflow`
     - `ETSY_SCOPE_TO_CASH_RELEASE_20261028` في `C:\Users\askgs\Documents\ETSY_SCOPE_TO_CASH_RELEASE_20261028`
   - ينفذ المهام ويدقق سلامة المشاريع محلياً دون أي خرق لسياسات الأمان أو تكلفة API.

3. **إضافة المتصفح (`extension/`):**
   - متوافقة تماماً مع معايير Google Chrome Manifest V3.
   - مخصصة للعمل داخل متصفح Chrome الشخصي للمالك لربط محادثات ChatGPT يدوياً عند رغبة المالك، دون الاعتماد على أدوات أتمتة غير مصرح بها.

---

## 2. عقد الأوامر المعتمد (Protocol Contract V1)

```json
{
  "protocol": "PROJECT_MANAGER_V1",
  "command_id": "unique-command-id",
  "source": "GENERAL_MANAGER",
  "target_project": "GITHUB",
  "action": "DISPATCH",
  "instruction": "فحص سلامة المستودع وحالة ملفات المشروع.",
  "requires_reply": true
}
```

---

## 3. قائمة الحقيقة التقنية (Truth Table)

| المكون / الوظيفة | الحالة الفعلية | الملاحظات |
| :--- | :---: | :--- |
| **خادم التنسيق المحلي** | **يعمل 100%** | يعمل على 8799، يسجل الإيصالات، يمنع التكرار والحلقات. |
| **التنسيق المحلي للمشاريع** | **يعمل 100%** | ينفذ المهام التشغيلية على مساحات عمل المشاريع محلياً بإيصالات موثقة. |
| **إضافة Chrome** | **جاهزة للعمل** | متوافقة مع Manifest V3 لربط التبويبات داخل متصفح المالك الشخصي. |
| **الوصول الآلي غير البشري لـ ChatGPT** | **محظور (`BLOCKED_BY_ACCESS_POLICY`)** | لا توجد واجهة رسمية، ومحمية بـ Cloudflare ضد الروبوتات. |
| **التكلفة المالية** | **صفر (\$0.00)** | لا يتم استخدام أي OpenAI API مدفوع، ولا استهلاك لأي حصص سحابية. |

---

## 4. أدوات التشغيل والاختبار

### تشغيل خادم المدير العام:
```cmd
start_gm.bat
```

### إيقاف الخادم بأمان:
```cmd
stop_gm.bat
```

### تشغيل الاختبارات المؤتمتة (15 اختباراً):
```bash
.\.venv\Scripts\pytest.exe -v
```

### تشغيل مهمة حقيقية على مشروع محلي مع إيصال SQLite:
```bash
.\.venv\Scripts\python.exe execute_real_project_task.py
```
