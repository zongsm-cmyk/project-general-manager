#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
برنامج تكوين المدير العام لمشاريع ChatGPT

الغرض: تهيئة محادثة المدير العام الحالية داخل ChatGPT لتصبح مركز قيادة
قادرًا على إدارة المشاريع الثمانية بواسطة الأدوات والتكاملات المصرح بها.

مهم: يجب أن يعمل هذا مباشرة في محادثة ChatGPT الحالية - وليس Claude.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# مسار المشروع الحالي (حيث يوجد هذا الملف)
PROJECT_ROOT = Path(__file__).parent

# تعريفات المشاريع الثمانية (متطابقة مع السجل)
PROJECT_DEFINITIONS = {
    "GM": {
        "name": "المدير العام للمشاريع",
        "status": "ACTIVE",
        "workspace_path": str(PROJECT_ROOT),
        "target_conversation_id": "6ae6dd41-105c-83e9-90ac-378e51c5e5af",  # وهذا هو مركز القيادة
        "role": "CENTER_OF_COMMAND"
    },
    "GITHUB": {
        "name": "GitHub / First Dollar Engine",
        "status": "ACTIVE",
        "workspace_path": "C:\\Users\\askgs\\Documents\\FirstDollarEngine",
        "target_conversation_id": "6ae6e433-1550-83ea-aedc-461ec36d966d",
        "role": "EXECUTE"
    },
    "GUMROAD": {
        "name": "Gumroad",
        "status": "ACTIVE",
        "workspace_path": "C:\\Users\\askgs\\Documents\\GUMROAD_CLI",
        "target_conversation_id": None,
        "role": "MONITOR"
    },
    "OPEN_SOURCE_AI_TOOLS": {
        "name": "Open-Source AI Tools",
        "status": "ACTIVE",
        "workspace_path": "C:\\Users\\askgs\\Documents\\OpenSource_Workflow",
        "target_conversation_id": None,
        "role": "EXECUTE"
    },
    "ETSY": {
        "name": "Etsy",
        "status": "UNCONFIGURED",
        "workspace_path": "C:\\Users\\askgs\\Documents\\ETSY_SCOPE_TO_CASH_RELEASE_20261028",
        "target_conversation_id": None,
        "role": "BLOCKED"
    },
    "AFFILIATE_MARKETING": {
        "name": "Affiliate Marketing",
        "status": "UNCONFIGURED",
        "workspace_path": None,
        "target_conversation_id": None,
        "role": "WAITING_SETUP"
    },
    "KAGGLE": {
        "name": "Kaggle",
        "status": "UNCONFIGURED",
        "workspace_path": None,
        "target_conversation_id": None,
        "role": "WAITING_SETUP"
    },
    "ALFAROUQ": {
        "name": "ALFAROUQ",
        "status": "UNCONFIGURED",
        "workspace_path": None,
        "target_conversation_id": None,
        "role": "PROTECTED"
    },
    "SOCIAL_MEDIA": {
        "name": "Social Media",
        "status": "UNCONFIGURED",
        "workspace_path": None,
        "target_conversation_id": None,
        "role": "MONITOR"
    }
}

class GM_ChatGPT_Orchestrator:
    """
    مركز القيادة للمدير العام داخل ChatGPT

    مسؤول عن:
    1. إدارة الأوامر الواردة من محادثة المدير العام الحالية
    2. توجيه الأوامر إلى المشاريع المناسبة
    3. تتبع حالة المشاريع وأداء المهام
    4. توليد التقارير التي تعود إلى المدير العام
    """

    def __init__(self):
        self.project_definitions = PROJECT_DEFINITIONS
        self.active_projects = self._get_active_projects()
        self.task_log = []

    def _get_active_projects(self):
        """إرجاع المشاريع التي لها دور نشط ووجهة محادثة محددة"""
        active = {}
        for key, info in self.project_definitions.items():
            if info["role"] not in ["BLOCKED", "WAITING_SETUP"] and info["target_conversation_id"]:
                active[key] = info
        return active

    def analyze_order_and_prioritize(self, instruction_arabic):
        """
        تحليل أمر من المدير العام وتوجيهه إلى المشروع المناسب

        المدخلات: أمر من المدير العام (باللغة العربية)
        الناتج: قائمة بالمشاريع التي سيتم استدعاؤها مع التبرير
        """
        print(f"[GM_ANALYSIS] أمر جديد: {instruction_arabic[:100]}...")

        # تحديد نوع الأمر
        order_type = self._classify_order(instruction_arabic)

        # الأولوية بناءً على الدور والمعرفة بالمشروع
        target_projects = self._select_target_projects(order_type, instruction_arabic)

        # التبرير
        rationale = f"التصنيف: {order_type}. المشاريع المستهدفة: {', '.join(target_projects.keys())}"

        return {
            "type": order_type,
            "target_projects": target_projects,
            "rationale": rationale,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _classify_order(self, instruction):
        """تصنيف الأمر إلى أنواع للعمل"""
        instruction_lower = instruction.lower()

        if any(word in instruction_lower for word in ["وضع", "تهيئة"]):
            return "CONFIGURATION"
        elif any(word in instruction_lower for word in ["حالة"]):
            return "STATUS_REPORT"
        elif any(word in instruction_lower for word in ["مراجعة"]):
            return "AUDIT_REVIEW"
        elif any(word in instruction_lower for word in ["توجيه", "تفويض"]):
            return "DISPATCH"
        elif any(word in instruction_lower for word in ["تتبع"]):
            return "MONITORING"
        elif any(word in instruction_lower for word in ["تنفيذ"]):
            return "EXECUTE"
        else:
            return "GENERAL_ORDER"

    def _select_target_projects(self, order_type, instruction):
        """اختيار المشاريع المناسبة للأمر"""
        target = {}

        # الأولوية: المشاريع النشطة التي لها مساحة عمل محددة
        for key, info in self.active_projects.items():
            if info["role"] == "EXECUTE":
                target[key] = info

        # تضمين المراقب لمهام المراجعة
        if order_type in ["AUDIT_REVIEW", "STATUS_REPORT", "MONITORING"]:
            for key, info in self.active_projects.items():
                if info["role"] in ["MONITOR", "EXECUTE"] and key not in target:
                    target[key] = info

        return target

    def dispatch_to_project(self, project_key, instruction, gm_command_id):
        """
        توجيه الأمر إلى مشروع محدد عبر قناة الوصول المصرح بها

        المدخلات:
        - project_key: مفتاح المشروع
        - instruction: الأمر
        - gm_command_id: معرف الأمر من المدير العام

        الناتج: حالة التنفيذ
        """
        project_info = self.project_definitions.get(project_key)
        if not project_info:
            return {
                "status": "FAILED",
                "error": f"المشروع '{project_key}' غير موجود في التعريفات"
            }

        if project_info["role"] == "BLOCKED":
            return {
                "status": "BLOCKED",
                "error": f"المشروع '{project_key}' غير نشط - لا يمكن تنفيذه"
            }

        # توليد معرف الأمر الخاص بالمشروع
        project_command_id = f"{gm_command_id}-{project_key}"

        # تنفيذ الأمر الخاص بالمشروع
        execution_result = self._execute_project_command(project_key, instruction, project_command_id)

        return {
            "project_key": project_key,
            "project_command_id": project_command_id,
            "status": execution_result["status"],
            "result": execution_result.get("result"),
            "error": execution_result.get("error"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _execute_project_command(self, project_key, instruction, command_id):
        """تنفيذ الأمر الخاص بالمشروع"""

        # في التنفيذ الحقيقي، هنا سنستخدم تكامل ChatGPT للاتصال
        # بالمشروع المطلوب (GitHub، Etsy، إلخ.) عبر الأدوات المصرح بها

        # لمحاكاة التنفيذ، سنقوم بتنفيذ الأمر محليًا
        if project_key == "GITHUB":
            # تنفيذ مهمة فحص GitHub
            result = self._github_task_execution(instruction, command_id)
        elif project_key == "GUMROAD":
            # تنفيذ مهمة فحص Gumroad
            result = self._gumroad_task_execution(instruction, command_id)
        elif project_key == "OPEN_SOURCE_AI_TOOLS":
            # تنفيذ مهمة فحص OpenSourceWorkflow
            result = self._opensource_task_execution(instruction, command_id)
        else:
            result = self._generic_task_execution(instruction, command_id)

        return result

    def _github_task_execution(self, instruction, command_id):
        """تنفيذ أمر GitHub"""
        workspace_path = "C:\\Users\\askgs\\Documents\\FirstDollarEngine"

        if not os.path.exists(workspace_path):
            return {"status": "FAILED", "error": "مساحة عمل GitHub غير موجودة"}

        # تنفيذ فحص تشغيل المدير العام المحلي للمشروع
        try:
            import local_adapter
            success, result = local_adapter.execute_project_task("GITHUB", workspace_path, instruction)
            return {"status": "SUCCESS" if success else "FAILED", "result": result}
        except Exception as e:
            return {"status": "FAILED", "error": f"خطأ في تنفيذ مهمة GitHub: {str(e)}"}

    def _gumroad_task_execution(self, instruction, command_id):
        """تنفيذ أمر Gumroad"""
        workspace_path = "C:\\Users\\askgs\\Documents\\GUMROAD_CLI"

        if not os.path.exists(workspace_path):
            return {"status": "FAILED", "error": "مساحة عمل Gumroad غير موجودة"}

        try:
            import local_adapter
            success, result = local_adapter.execute_project_task("GUMROAD", workspace_path, instruction)
            return {"status": "SUCCESS" if success else "FAILED", "result": result}
        except Exception as e:
            return {"status": "FAILED", "error": f"خطأ في تنفيذ مهمة Gumroad: {str(e)}"}

    def _opensource_task_execution(self, instruction, command_id):
        """تنفيذ أمر OpenSourceWorkflow"""
        workspace_path = "C:\\Users\\askgs\\Documents\\OpenSource_Workflow"

        if not os.path.exists(workspace_path):
            return {"status": "FAILED", "error": "مساحة عمل OpenSource غير موجودة"}

        try:
            import local_adapter
            success, result = local_adapter.execute_project_task("OPEN_SOURCE_AI_TOOLS", workspace_path, instruction)
            return {"status": "SUCCESS" if success else "FAILED", "result": result}
        except Exception as e:
            return {"status": "FAILED", "error": f"خطأ في تنفيذ مهمة OpenSource: {str(e)}"}

    def _generic_task_execution(self, instruction, command_id):
        """تنفيذ أمر عام"""
        return {"status": "COMPLETED", "result": "تم تنفيذ الأمر العام (محاكاة)"}

    def generate_status_report(self):
        """إنشاء تقرير حالة موحد للمشاريع الثمانية"""

        report_lines = []
        report_lines.append("تقرير حالة المدير العام")
        report_lines.append("=" * 60)
        report_lines.append(f"الوقت: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report_lines.append("")

        active_count = len(self.active_projects)
        blocked_count = sum(1 for p in self.project_definitions.values() if p["role"] == "BLOCKED")
        waiting_count = sum(1 for p in self.project_definitions.values() if p["role"] == "WAITING_SETUP")

        report_lines.append(f"إجمالي المشاريع: {len(self.project_definitions)}")
        report_lines.append(f"المشاريع النشطة: {active_count}")
        report_lines.append(f"المشاريع المحظورة: {blocked_count}")
        report_lines.append(f"في انتظار الإعداد: {waiting_count}")
        report_lines.append("")

        report_lines.append("تفاصيل المشاريع:")
        report_lines.append("-" * 40)

        for key, info in self.project_definitions.items():
            status_icon = "✅" if info["status"] == "ACTIVE" else "❌"
            role_icon = "⚡" if info["role"] == "EXECUTE" else "👁️" if info["role"] == "MONITOR" else "⏸️" if info["role"] == "BLOCKED" else "⏳"

            project_info = f"{status_icon} {role_icon} {key}: {info['name']}"

            if info["role"] in ["EXECUTE", "MONITOR"] and info["workspace_path"]:
                path_exists = "✅" if os.path.exists(info["workspace_path"]) else "❌"
                project_info += f" ({path_exists} {info['workspace_path'][:40]}...)"

            if info["target_conversation_id"]:
                project_info += f" [المحادثة: {info['target_conversation_id'][:8]}...]"

            report_lines.append(project_info)

        report_lines.append("")
        report_lines.append("التوصيات:")
        report_lines.append("-" * 40)

        # التوصيات
        for key, info in self.project_definitions.items():
            if info["role"] == "EXECUTE" and not os.path.exists(info.get("workspace_path", "")):
                report_lines.append(f"• تحقق من وجود مساحة عمل المشروع '{info['name']}'")

        if self.task_log:
            report_lines.append("")
            report_lines.append("آخر المهام:")
            report_lines.append("-" * 40)
            for task in self.task_log[-5:]:  # آخر 5 مهام
                report_lines.append(f"• {task['timestamp'][:19]} - {task['project_key']}: {task['action']} - {task['status']}")

        return "\n".join(report_lines)

def main():
    """دخول مدير العام للمشاريع داخل ChatGPT"""

    print("=" * 80)
    print("دخول مدير العام للمشاريع - التنشيط داخل ChatGPT")
    print("=" * 80)

    orchestrator = GM_ChatGPT_Orchestrator()

    # تسجيل حالة الدخول
    orchestrator.task_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "LOGIN",
        "project_key": "GM",
        "status": "SUCCESS",
        "result": "دخول مدير العام للمشاريع داخل ChatGPT - مركز القيادة نشط"
    })

    print("مركز القيادة نشط - مدير العام للمشاريع متصل")
    print(f"المشاريع النشطة: {len(orchestrator.active_projects)}")
    print(f"معرّف محادثة المدير العام: 6ae6dd41-105c-83e9-90ac-378e51c5e5af")
    print("")

    # اختبار القبول
    print("[TEST] إجراء فحص القبول...")
    status_report = orchestrator.generate_status_report()

    print("\n" + "=" * 80)
    print("تقرير حالة القبول الأولي:")
    print("=" * 80)
    print(status_report)

    # حفظ التكوين في ملف للرجوع إليه لاحقًا
    config_file = PROJECT_ROOT / "GM_CONFIG_STATE.json"
    config_state = {
        "orchestrator_initialized": True,
        "active_projects_count": len(orchestrator.active_projects),
        "gm_conversation_id": "6ae6dd41-105c-83e9-90ac-378e51c5e5af",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_state, f, ensure_ascii=False, indent=2)

    print(f"\n[CONFIG] تم حفظ حالة التكوين إلى: {config_file}")
    print("\n[READY] مدير العام للمشاريع جاهز لتلقي الأوامر")
    print("\nالأوامر التالية جاهزة للاستخدام:")
    print("1. راجع المشاريع الثمانية، وحدد الأعمال المتوقفة، ووجّه الموارد")
    print("2. أحصل على تقرير الحالة")
    print("3. قم بتشغيل المهام التشغيلية المحددة")

    return orchestrator

if __name__ == "__main__":
    orchestrator = main()