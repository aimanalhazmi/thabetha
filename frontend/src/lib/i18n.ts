import type { Language } from "./types";

/** All translation keys used across the app. */
export type TranslationKey =
  | "appName"
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
  | "askMerchantBot"
  | "signIn"
  | "signUp"
  | "email"
  | "password"
  | "name"
  | "phone"
  | "accountType"
  | "individual"
  | "business"
  | "taxId"
  | "commercialRegistration"
  | "signOut"
  | "createAccount"
  | "welcomeBack"
  | "alreadyHaveAccount"
  | "dontHaveAccount";

type Translations = Record<TranslationKey, string>;

const ar: Translations = {
  appName: "ثبتها",
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
  signIn: "تسجيل الدخول",
  signUp: "إنشاء حساب",
  email: "البريد الإلكتروني",
  password: "كلمة المرور",
  name: "الاسم",
  phone: "رقم الهاتف",
  accountType: "نوع الحساب",
  individual: "فردي",
  business: "تجاري",
  taxId: "الرقم الضريبي",
  commercialRegistration: "السجل التجاري",
  signOut: "تسجيل الخروج",
  createAccount: "إنشاء حساب جديد",
  welcomeBack: "مرحباً بعودتك",
  alreadyHaveAccount: "لديك حساب بالفعل؟",
  dontHaveAccount: "ليس لديك حساب؟",
};

const en: Translations = {
  appName: "Thabetha",
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
  signIn: "Sign In",
  signUp: "Sign Up",
  email: "Email",
  password: "Password",
  name: "Full Name",
  phone: "Phone Number",
  accountType: "Account Type",
  individual: "Individual",
  business: "Business",
  taxId: "Tax ID",
  commercialRegistration: "Commercial Registration",
  signOut: "Sign Out",
  createAccount: "Create Account",
  welcomeBack: "Welcome Back",
  alreadyHaveAccount: "Already have an account?",
  dontHaveAccount: "Don't have an account?",
};

const translations: Record<Language, Translations> = { ar, en };

/** Return the translated string for the given language and key. */
export function t(language: Language, key: TranslationKey): string {
  return translations[language]?.[key] ?? key;
}
