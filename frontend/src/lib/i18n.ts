import type { Language } from "./types";

/** All translation keys used across the app. */
export type TranslationKey =
  | "appName"
  | "currentUser"
  | "dashboard"
  | "debts"
  | "profile"
  | "qr"
  | "groups"
  | "ai"
  | "notifications"
  | "refresh"
  | "totalDebt"
  | "receivable"
  | "overdue"
  | "trustScore"
  | "noData"
  | "createDebt"
  | "debtorName"
  | "debtorId"
  | "amount"
  | "currency"
  | "description"
  | "dueDate"
  | "create"
  | "active"
  | "paid"
  | "accept"
  | "reject"
  | "markPaid"
  | "confirmPayment"
  | "save"
  | "aiEnabled"
  | "whatsapp"
  | "businessProfile"
  | "shopName"
  | "activityType"
  | "location"
  | "rotate"
  | "groupName"
  | "inviteUser"
  | "acceptInvite"
  | "voiceTranscript"
  | "draft"
  | "askMerchantBot";

type Translations = Record<TranslationKey, string>;

const ar: Translations = {
  appName: "ثبتها",
  currentUser: "المستخدم الحالي",
  dashboard: "لوحة التحكم",
  debts: "الديون",
  profile: "الملف الشخصي",
  qr: "رمز QR",
  groups: "المجموعات",
  ai: "الذكاء الاصطناعي",
  notifications: "الإشعارات",
  refresh: "تحديث",
  totalDebt: "إجمالي الدين",
  receivable: "المستحقات",
  overdue: "متأخر",
  trustScore: "نقاط الثقة",
  noData: "لا توجد بيانات",
  createDebt: "إنشاء دين",
  debtorName: "اسم المدين",
  debtorId: "معرف المدين",
  amount: "المبلغ",
  currency: "العملة",
  description: "الوصف",
  dueDate: "تاريخ الاستحقاق",
  create: "إنشاء",
  active: "نشط",
  paid: "مدفوع",
  accept: "قبول",
  reject: "رفض",
  markPaid: "تحديد كمدفوع",
  confirmPayment: "تأكيد الدفع",
  save: "حفظ",
  aiEnabled: "تفعيل الذكاء الاصطناعي",
  whatsapp: "واتساب",
  businessProfile: "الملف التجاري",
  shopName: "اسم المتجر",
  activityType: "نوع النشاط",
  location: "الموقع",
  rotate: "تدوير",
  groupName: "اسم المجموعة",
  inviteUser: "دعوة مستخدم",
  acceptInvite: "قبول الدعوة",
  voiceTranscript: "النص الصوتي",
  draft: "مسودة",
  askMerchantBot: "اسأل مساعد التاجر",
};

const en: Translations = {
  appName: "Thabetha",
  currentUser: "Current User",
  dashboard: "Dashboard",
  debts: "Debts",
  profile: "Profile",
  qr: "QR Code",
  groups: "Groups",
  ai: "AI Assistant",
  notifications: "Notifications",
  refresh: "Refresh",
  totalDebt: "Total Debt",
  receivable: "Receivable",
  overdue: "Overdue",
  trustScore: "Trust Score",
  noData: "No data",
  createDebt: "Create Debt",
  debtorName: "Debtor Name",
  debtorId: "Debtor ID",
  amount: "Amount",
  currency: "Currency",
  description: "Description",
  dueDate: "Due Date",
  create: "Create",
  active: "Active",
  paid: "Paid",
  accept: "Accept",
  reject: "Reject",
  markPaid: "Mark Paid",
  confirmPayment: "Confirm Payment",
  save: "Save",
  aiEnabled: "AI Enabled",
  whatsapp: "WhatsApp",
  businessProfile: "Business Profile",
  shopName: "Shop Name",
  activityType: "Activity Type",
  location: "Location",
  rotate: "Rotate",
  groupName: "Group Name",
  inviteUser: "Invite User",
  acceptInvite: "Accept Invite",
  voiceTranscript: "Voice Transcript",
  draft: "Draft",
  askMerchantBot: "Ask Merchant Bot",
};

const translations: Record<Language, Translations> = { ar, en };

/** Return the translated string for the given language and key. */
export function t(language: Language, key: TranslationKey): string {
  return translations[language]?.[key] ?? key;
}
