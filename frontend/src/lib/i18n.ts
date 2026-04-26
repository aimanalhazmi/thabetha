import type { Language } from './types';

/** All translation keys used across the app. */
export type TranslationKey =
  | 'appName'
  | 'dashboard'
  | 'debts'
  | 'profile'
  | 'qr'
  | 'groups'
  | 'ai'
  | 'notifications'
  | 'refresh'
  | 'totalDebt'
  | 'receivable'
  | 'overdue'
  | 'trustScore'
  | 'noData'
  | 'createDebt'
  | 'debtorName'
  | 'debtorId'
  | 'amount'
  | 'currency'
  | 'description'
  | 'dueDate'
  | 'create'
  | 'active'
  | 'paid'
  | 'accept'
  | 'reject'
  | 'markPaid'
  | 'confirmPayment'
  | 'save'
  | 'aiEnabled'
  | 'whatsapp'
  | 'businessProfile'
  | 'shopName'
  | 'activityType'
  | 'location'
  | 'rotate'
  | 'groupName'
  | 'inviteUser'
  | 'acceptInvite'
  | 'voiceTranscript'
  | 'draft'
  | 'askMerchantBot'
  | 'signIn'
  | 'signUp'
  | 'email'
  | 'password'
  | 'name'
  | 'phone'
  | 'accountType'
  | 'creditor'
  | 'debtor'
  | 'both'
  | 'taxId'
  | 'commercialRegistration'
  | 'signOut'
  | 'createAccount'
  | 'welcomeBack'
  | 'alreadyHaveAccount'
  | 'dontHaveAccount'
  | 'waitingForConfirmation'
  | 'delay'
  | 'checkEmail'
  | 'emailVerification'
  | 'emailVerificationDesc'
  | 'backToSignIn'
  | 'creditorDashboard'
  | 'debtorDashboard'
  | 'dueSoon'
  | 'debtors'
  | 'trustScoreDisclaimer'
  | 'delayAlerts'
  | 'recentDebts'
  | 'allStatuses'
  | 'noDebtsYet'
  | 'loading'
  | 'markRead'
  | 'rejected'
  | 'changeRequested'
  | 'paymentPendingConfirmation'
  | 'requestChange'
  | 'changeMessage'
  | 'newAmount'
  | 'newDueDate'
  | 'submitChangeRequest'
  | 'scanQr'
  | 'qrToken'
  | 'lookupDebtor'
  | 'debtorFound'
  | 'invalidQrToken'
  | 'creditorView'
  | 'debtorView'
  | 'confidence'
  | 'shopDescription'
  | 'cancel'
  | 'confirmReject'
  | 'from'
  | 'useDraft'
  | 'unread'
  | 'dueSoonWarning'
  | 'creditorLabel'
  | 'totalOwed'
  | 'myDebtors'
  | 'noUnread'
  | 'viewAll'
  | 'debtCreatedCta'
  | 'noDebtsCta';

type Translations = Record<TranslationKey, string>;

const ar: Translations = {
  appName: 'ثبتها',
  dashboard: 'لوحة التحكم',
  debts: 'الديون',
  profile: 'الملف الشخصي',
  qr: 'رمز QR',
  groups: 'المجموعات',
  ai: 'الذكاء الاصطناعي',
  notifications: 'الإشعارات',
  refresh: 'تحديث',
  totalDebt: 'إجمالي الدين',
  receivable: 'المستحقات',
  overdue: 'متأخر',
  trustScore: 'نقاط الثقة',
  noData: 'لا توجد بيانات',
  createDebt: 'إنشاء دين',
  debtorName: 'اسم المدين',
  debtorId: 'معرف المدين',
  amount: 'المبلغ',
  currency: 'العملة',
  description: 'الوصف',
  dueDate: 'تاريخ الاستحقاق',
  create: 'إنشاء',
  active: 'نشط',
  paid: 'مدفوع',
  accept: 'قبول',
  reject: 'رفض',
  markPaid: 'تحديد كمدفوع',
  confirmPayment: 'تأكيد الدفع',
  save: 'حفظ',
  aiEnabled: 'تفعيل الذكاء الاصطناعي',
  whatsapp: 'واتساب',
  businessProfile: 'الملف التجاري',
  shopName: 'اسم المتجر',
  activityType: 'نوع النشاط',
  location: 'الموقع',
  rotate: 'تدوير',
  groupName: 'اسم المجموعة',
  inviteUser: 'دعوة مستخدم',
  acceptInvite: 'قبول الدعوة',
  voiceTranscript: 'النص الصوتي',
  draft: 'مسودة',
  askMerchantBot: 'اسأل مساعد التاجر',
  signIn: 'تسجيل الدخول',
  signUp: 'إنشاء حساب',
  email: 'البريد الإلكتروني',
  password: 'كلمة المرور',
  name: 'الاسم',
  phone: 'رقم الهاتف',
  accountType: 'نوع الحساب',
  creditor: 'دائن (صاحب متجر)',
  debtor: 'مدين (عميل)',
  both: 'الاثنين معاً',
  taxId: 'الرقم الضريبي',
  commercialRegistration: 'السجل التجاري',
  signOut: 'تسجيل الخروج',
  createAccount: 'إنشاء حساب جديد',
  welcomeBack: 'مرحباً بعودتك',
  alreadyHaveAccount: 'لديك حساب بالفعل؟',
  dontHaveAccount: 'ليس لديك حساب؟',
  waitingForConfirmation: 'بانتظار التأكيد',
  delay: 'متأخر',
  checkEmail: 'تحقق من بريدك الإلكتروني',
  emailVerification: 'تأكيد البريد الإلكتروني',
  emailVerificationDesc: 'تم إرسال رابط التحقق إلى بريدك الإلكتروني. يرجى التحقق من بريدك لتفعيل حسابك.',
  backToSignIn: 'العودة لتسجيل الدخول',
  creditorDashboard: 'لوحة تحكم الدائن',
  debtorDashboard: 'لوحة تحكم المدين',
  dueSoon: 'قريب الاستحقاق',
  debtors: 'المدينون',
  trustScoreDisclaimer: 'مؤشر ثقة داخلي وليس تقييم ائتماني رسمي',
  delayAlerts: 'تنبيهات التأخير',
  recentDebts: 'الديون الأخيرة',
  allStatuses: 'جميع الحالات',
  noDebtsYet: 'لا توجد ديون حتى الآن',
  loading: 'جاري التحميل...',
  markRead: 'تحديد كمقروء',
  rejected: 'مرفوض',
  changeRequested: 'طلب تعديل',
  paymentPendingConfirmation: 'بانتظار تأكيد الدفع',
  requestChange: 'طلب تعديل',
  changeMessage: 'رسالة التعديل',
  newAmount: 'المبلغ الجديد (اختياري)',
  newDueDate: 'تاريخ استحقاق جديد (اختياري)',
  submitChangeRequest: 'إرسال طلب التعديل',
  scanQr: 'بحث برمز QR',
  qrToken: 'رمز QR',
  lookupDebtor: 'بحث عن المدين',
  debtorFound: 'تم العثور على المدين',
  invalidQrToken: 'رمز QR غير صالح أو منتهي الصلاحية',
  creditorView: 'عرض الدائن',
  debtorView: 'عرض المدين',
  confidence: 'الثقة',
  shopDescription: 'وصف المتجر',
  cancel: 'إلغاء',
  confirmReject: 'تأكيد الرفض',
  from: 'من',
  useDraft: 'إنشاء دين من هذه المسودة',
  unread: 'غير مقروء',
  dueSoonWarning: 'الاستحقاق خلال 3 أيام',
  creditorLabel: 'الدائن',
  totalOwed: 'إجمالي ما عليك',
  myDebtors: 'مدينوني',
  noUnread: 'لا إشعارات جديدة',
  viewAll: 'عرض الكل',
  debtCreatedCta: 'أنشئ دينك الأول لتبدأ المتابعة',
  noDebtsCta: 'لا توجد ديون في هذه الفئة',
};

const en: Translations = {
  appName: 'Thabetha',
  dashboard: 'Dashboard',
  debts: 'Debts',
  profile: 'Profile',
  qr: 'QR Code',
  groups: 'Groups',
  ai: 'AI Assistant',
  notifications: 'Notifications',
  refresh: 'Refresh',
  totalDebt: 'Total Debt',
  receivable: 'Receivable',
  overdue: 'Overdue',
  trustScore: 'Trust Score',
  noData: 'No data',
  createDebt: 'Create Debt',
  debtorName: 'Debtor Name',
  debtorId: 'Debtor ID',
  amount: 'Amount',
  currency: 'Currency',
  description: 'Description',
  dueDate: 'Due Date',
  create: 'Create',
  active: 'Active',
  paid: 'Paid',
  accept: 'Accept',
  reject: 'Reject',
  markPaid: 'Mark Paid',
  confirmPayment: 'Confirm Payment',
  save: 'Save',
  aiEnabled: 'AI Enabled',
  whatsapp: 'WhatsApp',
  businessProfile: 'Business Profile',
  shopName: 'Shop Name',
  activityType: 'Activity Type',
  location: 'Location',
  rotate: 'Rotate',
  groupName: 'Group Name',
  inviteUser: 'Invite User',
  acceptInvite: 'Accept Invite',
  voiceTranscript: 'Voice Transcript',
  draft: 'Draft',
  askMerchantBot: 'Ask Merchant Bot',
  signIn: 'Sign In',
  signUp: 'Sign Up',
  email: 'Email',
  password: 'Password',
  name: 'Full Name',
  phone: 'Phone Number',
  accountType: 'Account Type',
  creditor: 'Creditor (Shop Owner)',
  debtor: 'Debtor (Customer)',
  both: 'Both',
  taxId: 'Tax ID',
  commercialRegistration: 'Commercial Registration',
  signOut: 'Sign Out',
  createAccount: 'Create Account',
  welcomeBack: 'Welcome Back',
  alreadyHaveAccount: 'Already have an account?',
  dontHaveAccount: "Don't have an account?",
  waitingForConfirmation: 'Waiting for Confirmation',
  delay: 'Delayed',
  checkEmail: 'Check Your Email',
  emailVerification: 'Email Verification',
  emailVerificationDesc: 'A verification link has been sent to your email. Please check your inbox to activate your account.',
  backToSignIn: 'Back to Sign In',
  creditorDashboard: 'Creditor Dashboard',
  debtorDashboard: 'Debtor Dashboard',
  dueSoon: 'Due Soon',
  debtors: 'Debtors',
  trustScoreDisclaimer: 'Internal trust indicator, not an official credit score',
  delayAlerts: 'Delay Alerts',
  recentDebts: 'Recent Debts',
  allStatuses: 'All Statuses',
  noDebtsYet: 'No debts yet',
  loading: 'Loading...',
  markRead: 'Mark as Read',
  rejected: 'Rejected',
  changeRequested: 'Change Requested',
  paymentPendingConfirmation: 'Payment Pending Confirmation',
  requestChange: 'Request Change',
  changeMessage: 'Change Message',
  newAmount: 'New Amount (optional)',
  newDueDate: 'New Due Date (optional)',
  submitChangeRequest: 'Submit Change Request',
  scanQr: 'Scan QR Code',
  qrToken: 'QR Token',
  lookupDebtor: 'Look Up Debtor',
  debtorFound: 'Debtor Found',
  invalidQrToken: 'Invalid or expired QR token',
  creditorView: 'Creditor View',
  debtorView: 'Debtor View',
  confidence: 'Confidence',
  shopDescription: 'Shop Description',
  cancel: 'Cancel',
  confirmReject: 'Confirm Reject',
  from: 'From',
  useDraft: 'Create Debt from Draft',
  unread: 'Unread',
  dueSoonWarning: 'Due within 3 days',
  creditorLabel: 'Creditor',
  totalOwed: 'Total You Owe',
  myDebtors: 'My Debtors',
  noUnread: 'No new notifications',
  viewAll: 'View All',
  debtCreatedCta: 'Create your first debt to start tracking',
  noDebtsCta: 'No debts in this category',
};

const translations: Record<Language, Translations> = { ar, en };

/** Return the translated string for the given language and key. */
export function t(language: Language, key: TranslationKey): string {
  return translations[language]?.[key] ?? key;
}
