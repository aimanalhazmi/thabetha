import type { Language } from './types';

/** All translation keys used across the app. */
export type TranslationKey =
  | 'appName'
  | 'tagline'
  | 'dashboard'
  | 'debts'
  | 'profile'
  | 'qr'
  | 'qrProfile'
  | 'qrScanner'
  | 'groups'
  | 'ai'
  | 'notifications'
  | 'settings'
  | 'refresh'
  | 'totalDebt'
  | 'receivable'
  | 'overdue'
  | 'commitmentIndicator'
  | 'commitmentDisclaimer'
  | 'noData'
  | 'createDebt'
  | 'debtorName'
  | 'debtorId'
  | 'amount'
  | 'currency'
  | 'description'
  | 'dueDate'
  | 'create'
  | 'cancel'
  | 'cancel_debt'
  | 'cancel_debt_confirm_title'
  | 'cancel_debt_confirm_body'
  | 'cancel_message_optional'
  | 'cancelled_successfully'
  | 'cancel_debt_state_changed'
  | 'active'
  | 'paid'
  | 'accept'
  | 'requestEdit'
  | 'approveEdit'
  | 'rejectEdit'
  | 'editReason'
  | 'editReasonPlaceholder'
  | 'proposedAmount'
  | 'proposedDueDate'
  | 'optional'
  | 'sendEditRequest'
  | 'editRequestFromDebtor'
  | 'noEditRequestDetails'
  | 'creditorReply'
  | 'creditorReplyPlaceholder'
  | 'currentValue'
  | 'requestedValue'
  | 'proposedDescription'
  | 'finalAmount'
  | 'finalDueDate'
  | 'finalDescription'
  | 'approveAndSave'
  | 'debtorProposed'
  | 'awaitingCreditor'
  | 'yourEditRequest'
  | 'creditorApprovedEdit'
  | 'creditorRejectedEdit'
  | 'newTerms'
  | 'reviewAndAccept'
  | 'reminderDates'
  | 'addReminder'
  | 'reminderPresetOnDue'
  | 'reminderPresetPlus1'
  | 'reminderPresetPlus3'
  | 'reminderPresetPlus7'
  | 'reminderPresetPlus14'
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
  | 'groupsCreate'
  | 'groupsCreateGroup'
  | 'groupsInvite'
  | 'groupsInviteByEmailOrPhone'
  | 'groupsAccept'
  | 'groupsDecline'
  | 'groupsLeave'
  | 'groupsRename'
  | 'groupsTransferOwnership'
  | 'groupsDelete'
  | 'groupsRevokeInvite'
  | 'groupsMyGroups'
  | 'groupsPendingInvitations'
  | 'groupsNoPendingInvitations'
  | 'groupsNoGroupsYet'
  | 'groupsMembers'
  | 'groupsPendingInvites'
  | 'groupsDebts'
  | 'groupsOwner'
  | 'groupsMemberCount'
  | 'groupsNoGroupOption'
  | 'groupsSelectorLabel'
  | 'settingsGroupsFeature'
  | 'settingsGroupsFeatureHint'
  | 'errorNotPlatformUser'
  | 'errorAlreadyMember'
  | 'errorInviteToSelf'
  | 'errorGroupFull'
  | 'errorOwnerCannotLeave'
  | 'errorNotAGroupMember'
  | 'errorNotGroupOwner'
  | 'errorGroupHasDebts'
  | 'errorGroupTagLocked'
  | 'errorNotInSharedGroup'
  | 'errorSameOwner'
  | 'errorNoPendingInvite'
  | 'errorIdentifierAmbiguous'
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
  | 'pendingConfirmation'
  | 'editRequested'
  | 'paymentPendingConfirmation'
  | 'cancelled'
  | 'checkEmail'
  | 'emailVerification'
  | 'emailVerificationDesc'
  | 'backToSignIn'
  | 'creditorDashboard'
  | 'debtorDashboard'
  | 'dueSoon'
  | 'debtors'
  | 'overdueAlerts'
  | 'recentDebts'
  | 'allStatuses'
  | 'noDebtsYet'
  | 'noNotificationsYet'
  | 'loading'
  | 'errorGeneric'
  | 'errorLoadDebts'
  | 'errorLoadDashboard'
  | 'errorLoadNotifications'
  | 'errorTransitionStateChanged'
  | 'errorTransitionForbidden'
  | 'selectAccountType'
  | 'selectAccountTypeDesc'
  | 'shopOwner'
  | 'shopOwnerDesc'
  | 'customer'
  | 'customerDesc'
  | 'continueAction'
  | 'back'
  | 'upgradeToAi'
  | 'upgradeToAiDesc'
  | 'upgradeNow'
  | 'aiActive'
  | 'scanCustomerQr'
  | 'scanCustomerQrDesc'
  | 'enterToken'
  | 'lookup'
  | 'customerProfile'
  | 'unpaidDebts'
  | 'myDebtStatus'
  | 'landingHeadline'
  | 'landingPitch'
  | 'getStarted'
  | 'learnMore'
  | 'forCreditors'
  | 'forDebtors'
  | 'creditorPitch'
  | 'debtorPitch'
  | 'receiptUpload'
  | 'receiptUploadHint'
  | 'receiptAdd'
  | 'receiptRemove'
  | 'receiptRetry'
  | 'receiptOpen'
  | 'receiptList'
  | 'receiptNone'
  | 'receiptLoading'
  | 'receiptLoadFailed'
  | 'receiptUploadFailed'
  | 'receiptUploadRetry'
  | 'receiptUploading'
  | 'receiptUploaded'
  | 'receiptTooLarge'
  | 'receiptUnsupported'
  | 'receiptLargeWarning'
  | 'receiptArchived'
  | 'receiptAvailable'
  | 'qrExpiredAskRefresh'
  | 'cannotBillSelf'
  | 'clearDebtor'
  | 'scannedDebtorLabel'
  | 'createDebtForPerson'
  | 'languageLabel'
  | 'switchLanguage'
  | 'navMenu'
  | 'debtTrackerSubtitle'
  | 'toastEditRequestSent'
  | 'toastDebtAccepted'
  | 'toastEditApproved'
  | 'originalTermsStand'
  | 'toastEditRejected'
  | 'toastDebtCreated'
  | 'toastReceiptUploaded'
  | 'rescan'
  | 'debtorIdPlaceholder'
  | 'toastPaymentRequested'
  | 'toastPaymentConfirmed'
  | 'toastProfileSaved'
  | 'inbucketDevHint'
  | 'phonePlaceholder'
  | 'reminderDatePlaceholder'
  | 'whatsapp_status_attempted'
  | 'whatsapp_status_delivered'
  | 'whatsapp_status_failed'
  | 'whatsapp_failed_reason_recipient_blocked'
  | 'whatsapp_failed_reason_invalid_phone'
  | 'whatsapp_failed_reason_template_not_approved'
  | 'whatsapp_failed_reason_template_param_mismatch'
  | 'whatsapp_failed_reason_provider_4xx'
  | 'whatsapp_failed_reason_provider_5xx'
  | 'whatsapp_failed_reason_network_error'
  | 'whatsapp_failed_reason_no_template'
  | 'whatsapp_failed_reason_no_phone_number'
  | 'payOnline'
  | 'creditorReceives'
  | 'paymentProcessing'
  | 'paymentInProgress'
  | 'paymentFailed'
  | 'paymentSucceeded'
  | 'gatewayUnavailable'
  | 'paymentPendingTitle'
  | 'paymentPendingBody'
  | 'feeLabel'
  | 'grossAmount'
  // Phase 9 — group settlement / auto-netting
  | 'settlementCtaSettleGroup'
  | 'settlementCtaNothingToSettle'
  | 'settlementStatusOpen'
  | 'settlementStatusRejected'
  | 'settlementStatusExpired'
  | 'settlementStatusSettled'
  | 'settlementStatusFailed'
  | 'settlementRolePayer'
  | 'settlementRoleReceiver'
  | 'settlementRoleObserver'
  | 'settlementConfirm'
  | 'settlementReject'
  | 'settlementExpiresIn'
  | 'settlementTransfersHeading'
  | 'settlementProposedTitle'
  | 'settlementReviewTitle'
  | 'settlementCtaTryAgain'
  | 'errorOpenProposalExists'
  | 'errorMixedCurrency'
  | 'errorNothingToSettle'
  | 'errorNotARequiredParty'
  | 'errorAlreadyResponded'
  | 'errorProposalNotOpen'
  | 'errorStaleSnapshot'
  | 'errorLeaveBlockedByOpenProposal';

type Translations = Record<TranslationKey, string>;

const ar: Translations = {
  appName: 'ثبتها',
  tagline: 'دفتر الديون الذي يؤكّده الطرفان',
  dashboard: 'لوحة التحكم',
  debts: 'الديون',
  profile: 'الملف الشخصي',
  qr: 'رمز QR',
  qrProfile: 'ملفي عبر QR',
  qrScanner: 'ماسح رمز العميل',
  groups: 'المجموعات',
  ai: 'الذكاء الاصطناعي',
  notifications: 'الإشعارات',
  settings: 'الإعدادات',
  refresh: 'تحديث',
  totalDebt: 'إجمالي الدين',
  receivable: 'المستحقات',
  overdue: 'متأخر',
  commitmentIndicator: 'مؤشر الالتزام',
  commitmentDisclaimer: 'مؤشر داخلي للالتزام بالسداد، وليس تقييمًا ائتمانيًا رسميًا',
  noData: 'لا توجد بيانات',
  createDebt: 'إنشاء دين',
  debtorName: 'اسم المدين',
  debtorId: 'معرف المدين',
  amount: 'المبلغ',
  currency: 'العملة',
  description: 'الوصف',
  dueDate: 'تاريخ الاستحقاق',
  create: 'إنشاء',
  cancel: 'إلغاء',
  cancel_debt: 'إلغاء الدين',
  cancel_debt_confirm_title: 'إلغاء هذا الدين؟',
  cancel_debt_confirm_body: 'سيتم إخطار المَدين. لا يمكن التراجع عن هذا الإجراء.',
  cancel_message_optional: 'أضف سببًا اختياريًا (200 حرفًا كحد أقصى)',
  cancelled_successfully: 'تم إلغاء الدين',
  cancel_debt_state_changed: 'لم يعد بالإمكان إلغاء هذا الدين — تغيّرت حالته.',
  active: 'نشط',
  paid: 'مدفوع',
  accept: 'قبول',
  requestEdit: 'طلب تعديل',
  approveEdit: 'الموافقة على التعديل',
  rejectEdit: 'رفض التعديل',
  editReason: 'سبب طلب التعديل',
  editReasonPlaceholder: 'اكتب سبب طلبك للتعديل ليطّلع عليه الدائن',
  proposedAmount: 'المبلغ المقترح',
  proposedDueDate: 'تاريخ الاستحقاق المقترح',
  optional: 'اختياري',
  sendEditRequest: 'إرسال طلب التعديل',
  editRequestFromDebtor: 'طلب تعديل من المدين',
  noEditRequestDetails: 'لا توجد تفاصيل لطلب التعديل',
  creditorReply: 'رسالتك للمدين',
  creditorReplyPlaceholder: 'اشرح قرارك ليتلقّاه المدين مع التعديلات',
  currentValue: 'الحالي',
  requestedValue: 'المقترح',
  proposedDescription: 'الوصف المقترح',
  finalAmount: 'المبلغ النهائي',
  finalDueDate: 'تاريخ الاستحقاق النهائي',
  finalDescription: 'الوصف النهائي',
  approveAndSave: 'الموافقة وحفظ التعديلات',
  debtorProposed: 'اقتراح المدين',
  awaitingCreditor: 'بانتظار رد الدائن',
  yourEditRequest: 'طلب التعديل الخاص بك',
  creditorApprovedEdit: 'وافق الدائن على التعديل',
  creditorRejectedEdit: 'رفض الدائن التعديل',
  newTerms: 'الشروط الجديدة',
  reviewAndAccept: 'راجع الشروط وأكّدها',
  reminderDates: 'تواريخ التذكير',
  addReminder: 'إضافة تذكير',
  reminderPresetOnDue: 'في تاريخ الاستحقاق',
  reminderPresetPlus1: 'بعد يوم',
  reminderPresetPlus3: 'بعد ٣ أيام',
  reminderPresetPlus7: 'بعد ٧ أيام',
  reminderPresetPlus14: 'بعد ١٤ يومًا',
  markPaid: 'تحديد كمدفوع',
  confirmPayment: 'تأكيد استلام الدفع',
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
  groupsCreate: 'إنشاء مجموعة',
  groupsCreateGroup: 'إنشاء مجموعة جديدة',
  groupsInvite: 'دعوة',
  groupsInviteByEmailOrPhone: 'البريد الإلكتروني أو رقم الهاتف',
  groupsAccept: 'قبول',
  groupsDecline: 'رفض',
  groupsLeave: 'مغادرة المجموعة',
  groupsRename: 'إعادة تسمية',
  groupsTransferOwnership: 'نقل الملكية',
  groupsDelete: 'حذف المجموعة',
  groupsRevokeInvite: 'إلغاء الدعوة',
  groupsMyGroups: 'مجموعاتي',
  groupsPendingInvitations: 'دعوات معلقة',
  groupsNoPendingInvitations: 'لا توجد دعوات معلقة',
  groupsNoGroupsYet: 'لم تنضم إلى أي مجموعة بعد',
  groupsMembers: 'الأعضاء',
  groupsPendingInvites: 'الدعوات المعلقة',
  groupsDebts: 'ديون المجموعة',
  groupsOwner: 'المالك',
  groupsMemberCount: 'عدد الأعضاء',
  groupsNoGroupOption: 'بدون مجموعة (خاص)',
  groupsSelectorLabel: 'مجموعة (اختياري)',
  settingsGroupsFeature: 'ميزة المجموعات',
  settingsGroupsFeatureHint: 'إظهار المجموعات في القائمة الرئيسية. تعطيلها لا يحذف عضوياتك.',
  errorNotPlatformUser: 'لا يوجد مستخدم بهذا البريد أو الهاتف. اطلب منه التسجيل أولاً.',
  errorAlreadyMember: 'هذا المستخدم عضو بالفعل أو لديه دعوة معلقة.',
  errorInviteToSelf: 'لا يمكنك دعوة نفسك.',
  errorGroupFull: 'المجموعة ممتلئة (الحد الأقصى ٢٠ عضوًا).',
  errorOwnerCannotLeave: 'يجب على المالك نقل الملكية قبل المغادرة.',
  errorNotAGroupMember: 'لست عضوًا مقبولًا في هذه المجموعة.',
  errorNotGroupOwner: 'هذه العملية متاحة لمالك المجموعة فقط.',
  errorGroupHasDebts: 'لا يمكن حذف المجموعة وفيها ديون مرتبطة.',
  errorGroupTagLocked: 'لا يمكن تغيير المجموعة بعد قبول المدين للدين.',
  errorNotInSharedGroup: 'الطرفان ليسا في نفس المجموعة.',
  errorSameOwner: 'هذا الشخص هو المالك الحالي بالفعل.',
  errorNoPendingInvite: 'لا توجد دعوة معلقة.',
  errorIdentifierAmbiguous: 'أدخل واحدًا فقط: المعرف، البريد، أو الهاتف.',
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
  pendingConfirmation: 'بانتظار التأكيد',
  editRequested: 'طلب تعديل',
  paymentPendingConfirmation: 'بانتظار تأكيد الدفع',
  cancelled: 'ملغي',
  checkEmail: 'تحقق من بريدك الإلكتروني',
  emailVerification: 'تأكيد البريد الإلكتروني',
  emailVerificationDesc: 'تم إرسال رابط التحقق إلى بريدك الإلكتروني. يرجى التحقق من بريدك لتفعيل حسابك.',
  backToSignIn: 'العودة لتسجيل الدخول',
  creditorDashboard: 'لوحة تحكم الدائن',
  debtorDashboard: 'لوحة تحكم المدين',
  dueSoon: 'قريب الاستحقاق',
  debtors: 'المدينون',
  overdueAlerts: 'تنبيهات التأخر',
  recentDebts: 'الديون الأخيرة',
  allStatuses: 'جميع الحالات',
  noDebtsYet: 'لا توجد ديون حتى الآن',
  noNotificationsYet: 'لا توجد إشعارات حتى الآن',
  errorGeneric: 'حدث خطأ، حاول مرة أخرى.',
  errorLoadDebts: 'تعذّر تحميل الديون. حاول مرة أخرى.',
  errorLoadDashboard: 'تعذّر تحميل لوحة التحكم. حاول مرة أخرى.',
  errorLoadNotifications: 'تعذّر تحميل الإشعارات. حاول مرة أخرى.',
  errorTransitionStateChanged: 'تغيّرت حالة هذا الدين — يرجى التحديث.',
  errorTransitionForbidden: 'غير مسموح لك بتنفيذ هذا الإجراء.',
  loading: 'جاري التحميل...',
  selectAccountType: 'اختر نوع الحساب',
  selectAccountTypeDesc: 'كيف ستستخدم ثبتها؟',
  shopOwner: 'صاحب متجر',
  shopOwnerDesc: 'أدير ديون عملائي وأصدر فواتير ومسح QR',
  customer: 'عميل',
  customerDesc: 'أتابع ديوني وأؤكد عمليات الدفع',
  continueAction: 'متابعة',
  back: 'رجوع',
  upgradeToAi: 'ترقية لخطة الذكاء الاصطناعي',
  upgradeToAiDesc: 'إنشاء الديون بالصوت، تلخيصات ذكية، وتوصيات للعملاء.',
  upgradeNow: 'ترقية الآن',
  aiActive: 'الذكاء الاصطناعي مفعّل',
  scanCustomerQr: 'مسح رمز العميل',
  scanCustomerQrDesc: 'أدخل رمز QR الخاص بالعميل لفتح ملفه وإنشاء دين له.',
  enterToken: 'أدخل الرمز',
  lookup: 'بحث',
  customerProfile: 'ملف العميل',
  unpaidDebts: 'الديون غير المدفوعة',
  myDebtStatus: 'حالة ديوني',
  landingHeadline: 'دفتر ديون رقمي يؤكده الطرفان',
  landingPitch: 'استبدل دفتر الديون الورقي بسجل بسيط، عربي أولاً، يؤكده كلٌ من الدائن والمدين، مع مؤشر التزام داخلي وتذكيرات تلقائية.',
  getStarted: 'ابدأ الآن',
  learnMore: 'تعرف على المزيد',
  forCreditors: 'للدائنين',
  forDebtors: 'للمدينين',
  creditorPitch: 'أنشئ ديونًا، امسح QR العميل، استلم تأكيد الدفع، وراقب المستحقات والمتأخر.',
  debtorPitch: 'تابع ديونك في مكان واحد، أكد القبول، اطلب تعديلًا، وأخطر دائنك عند السداد.',
  receiptUpload: 'إيصالات الدين',
  receiptUploadHint: 'أرفق صورًا أو ملفات PDF حتى ٥ م.ب لكل ملف',
  receiptAdd: 'إضافة إيصال',
  receiptRemove: 'إزالة',
  receiptRetry: 'إعادة المحاولة',
  receiptOpen: 'فتح',
  receiptList: 'الإيصالات',
  receiptNone: 'لا توجد إيصالات',
  receiptLoading: 'جاري تحميل الإيصالات...',
  receiptLoadFailed: 'تعذر تحميل الإيصالات',
  receiptUploadFailed: 'فشل رفع بعض الإيصالات. يمكنك إعادة المحاولة من بطاقة الدين.',
  receiptUploadRetry: 'إعادة رفع الإيصالات الفاشلة',
  receiptUploading: 'جاري الرفع',
  receiptUploaded: 'تم الرفع',
  receiptTooLarge: 'الحد الأقصى للملف ٥ م.ب',
  receiptUnsupported: 'ارفع صورة أو ملف PDF فقط',
  receiptLargeWarning: 'ملف كبير، قد يستغرق الرفع وقتًا أطول',
  receiptArchived: 'مؤرشف',
  receiptAvailable: 'متاح',
  qrExpiredAskRefresh: 'انتهت صلاحية رمز QR، اطلب من العميل تحديث رمزه',
  cannotBillSelf: 'لا يمكنك تسجيل دين على نفسك',
  clearDebtor: 'تغيير المدين',
  scannedDebtorLabel: 'تم التحقق عبر QR',
  createDebtForPerson: 'إنشاء دين لهذا الشخص',
  languageLabel: 'اللغة',
  switchLanguage: 'English',
  navMenu: 'القائمة',
  debtTrackerSubtitle: 'متتبع الديون',
  toastEditRequestSent: 'تم إرسال طلب التعديل',
  toastDebtAccepted: 'تم قبول الدين',
  toastEditApproved: 'تمت الموافقة على التعديل',
  originalTermsStand: 'الشروط الأصلية سارية',
  toastEditRejected: 'تم رفض التعديل',
  toastDebtCreated: 'تم إنشاء الدين',
  toastReceiptUploaded: 'تم رفع الإيصال',
  rescan: 'مسح من جديد',
  debtorIdPlaceholder: 'معرف المدين (اختياري)',
  toastPaymentRequested: 'تم طلب تأكيد الدفع',
  toastPaymentConfirmed: 'تم تأكيد الدفع',
  toastProfileSaved: 'تم حفظ الملف الشخصي',
  inbucketDevHint: '📧 تحقق من Inbucket على المنفذ 55324',
  phonePlaceholder: '+966XXXXXXXXX',
  reminderDatePlaceholder: 'YYYY-MM-DD, YYYY-MM-DD',
  whatsapp_status_attempted: 'أُرسل عبر واتساب — بانتظار التأكيد',
  whatsapp_status_delivered: 'وصل عبر واتساب',
  whatsapp_status_failed: 'فشل عبر واتساب',
  whatsapp_failed_reason_recipient_blocked: 'المستلم حظَر الإرسال',
  whatsapp_failed_reason_invalid_phone: 'رقم الجوال غير صالح',
  whatsapp_failed_reason_template_not_approved: 'القالب غير معتمد',
  whatsapp_failed_reason_template_param_mismatch: 'بيانات القالب غير مطابقة',
  whatsapp_failed_reason_provider_4xx: 'رفض من مزوّد واتساب',
  whatsapp_failed_reason_provider_5xx: 'تعذّر الإرسال — جرّب لاحقًا',
  whatsapp_failed_reason_network_error: 'خطأ في الشبكة',
  whatsapp_failed_reason_no_template: 'لا يوجد قالب لهذا الإشعار',
  whatsapp_failed_reason_no_phone_number: 'لا يوجد رقم جوال للمستلم',
  payOnline: 'ادفع إلكترونيًا',
  creditorReceives: 'سيستلم الدائن',
  paymentProcessing: 'جاري معالجة الدفع...',
  paymentInProgress: 'لديك عملية دفع جارية، يرجى الانتظار.',
  paymentFailed: 'فشلت عملية الدفع — يمكنك إعادة المحاولة.',
  paymentSucceeded: 'تم الدفع بنجاح!',
  gatewayUnavailable: 'بوابة الدفع غير متاحة حاليًا، حاول لاحقًا.',
  paymentPendingTitle: 'الدفع قيد المعالجة',
  paymentPendingBody: 'لم يُؤكَّد الدفع بعد — ستُحدَّث الحالة تلقائيًا عند وصول التأكيد.',
  feeLabel: 'رسوم البوابة',
  grossAmount: 'المبلغ الإجمالي',
  // Phase 9 — group settlement / auto-netting
  settlementCtaSettleGroup: 'تسوية المجموعة',
  settlementCtaNothingToSettle: 'لا توجد ديون نشطة للتسوية.',
  settlementStatusOpen: 'مفتوح',
  settlementStatusRejected: 'مرفوض',
  settlementStatusExpired: 'منتهي الصلاحية',
  settlementStatusSettled: 'تمت التسوية',
  settlementStatusFailed: 'فشلت التسوية',
  settlementRolePayer: 'دافع',
  settlementRoleReceiver: 'مستلم',
  settlementRoleObserver: 'مشاهد',
  settlementConfirm: 'تأكيد',
  settlementReject: 'رفض',
  settlementExpiresIn: 'تنتهي خلال',
  settlementTransfersHeading: 'التحويلات المقترحة',
  settlementProposedTitle: 'اقتراح تسوية',
  settlementReviewTitle: 'مراجعة التسوية',
  settlementCtaTryAgain: 'حاول مجددًا',
  errorOpenProposalExists: 'يوجد اقتراح تسوية مفتوح في هذه المجموعة.',
  errorMixedCurrency: 'لا يمكن تسوية ديون بعملات مختلفة تلقائيًا.',
  errorNothingToSettle: 'لا توجد ديون قابلة للتسوية في هذه المجموعة.',
  errorNotARequiredParty: 'لست طرفًا مطلوبًا في هذا الاقتراح.',
  errorAlreadyResponded: 'لقد قمت بالرد على هذا الاقتراح بالفعل.',
  errorProposalNotOpen: 'الاقتراح لم يعد مفتوحًا.',
  errorStaleSnapshot: 'تغيرت حالة أحد الديون، يرجى إعادة المحاولة.',
  errorLeaveBlockedByOpenProposal: 'لا يمكنك مغادرة المجموعة وأنت طرف في اقتراح تسوية مفتوح.',
};

const en: Translations = {
  appName: 'Thabetha',
  tagline: 'The debt notebook both sides confirm',
  dashboard: 'Dashboard',
  debts: 'Debts',
  profile: 'Profile',
  qr: 'QR Code',
  qrProfile: 'My QR profile',
  qrScanner: 'QR scanner',
  groups: 'Groups',
  ai: 'AI Assistant',
  notifications: 'Notifications',
  settings: 'Settings',
  refresh: 'Refresh',
  totalDebt: 'Total Debt',
  receivable: 'Receivable',
  overdue: 'Overdue',
  commitmentIndicator: 'Commitment Indicator',
  commitmentDisclaimer: 'Internal commitment indicator, not an official credit score',
  noData: 'No data',
  createDebt: 'Create Debt',
  debtorName: 'Debtor Name',
  debtorId: 'Debtor ID',
  amount: 'Amount',
  currency: 'Currency',
  description: 'Description',
  dueDate: 'Due Date',
  create: 'Create',
  cancel: 'Cancel',
  cancel_debt: 'Cancel debt',
  cancel_debt_confirm_title: 'Cancel this debt?',
  cancel_debt_confirm_body: 'The debtor will be notified. This cannot be undone.',
  cancel_message_optional: 'Add an optional reason (max 200 characters)',
  cancelled_successfully: 'Debt cancelled',
  cancel_debt_state_changed: 'This debt can no longer be cancelled — its status changed.',
  active: 'Active',
  paid: 'Paid',
  accept: 'Accept',
  requestEdit: 'Request edit',
  approveEdit: 'Approve edit',
  rejectEdit: 'Reject edit',
  editReason: 'Reason for the edit',
  editReasonPlaceholder: 'Explain why you want this debt edited — the creditor will see this message',
  proposedAmount: 'Proposed amount',
  proposedDueDate: 'Proposed due date',
  optional: 'optional',
  sendEditRequest: 'Send edit request',
  editRequestFromDebtor: 'Edit request from debtor',
  noEditRequestDetails: 'No details available for this edit request',
  creditorReply: 'Your reply to the debtor',
  creditorReplyPlaceholder: 'Explain your decision — the debtor will receive this with the updated terms',
  currentValue: 'Current',
  requestedValue: 'Requested',
  proposedDescription: 'Proposed description',
  finalAmount: 'Final amount',
  finalDueDate: 'Final due date',
  finalDescription: 'Final description',
  approveAndSave: 'Approve & save changes',
  debtorProposed: "Debtor's proposal",
  awaitingCreditor: "Awaiting creditor's reply",
  yourEditRequest: 'Your edit request',
  creditorApprovedEdit: 'Creditor approved your edit',
  creditorRejectedEdit: 'Creditor declined your edit',
  newTerms: 'New terms',
  reviewAndAccept: 'Review the terms and confirm',
  reminderDates: 'Reminders',
  addReminder: 'Add reminder',
  reminderPresetOnDue: 'On due date',
  reminderPresetPlus1: '+1 day',
  reminderPresetPlus3: '+3 days',
  reminderPresetPlus7: '+7 days',
  reminderPresetPlus14: '+14 days',
  markPaid: 'Mark paid',
  confirmPayment: 'Confirm payment',
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
  groupsCreate: 'Create group',
  groupsCreateGroup: 'Create a new group',
  groupsInvite: 'Invite',
  groupsInviteByEmailOrPhone: 'Email or phone',
  groupsAccept: 'Accept',
  groupsDecline: 'Decline',
  groupsLeave: 'Leave group',
  groupsRename: 'Rename',
  groupsTransferOwnership: 'Transfer ownership',
  groupsDelete: 'Delete group',
  groupsRevokeInvite: 'Revoke',
  groupsMyGroups: 'My groups',
  groupsPendingInvitations: 'Pending invitations',
  groupsNoPendingInvitations: 'No pending invitations',
  groupsNoGroupsYet: "You haven't joined any groups yet",
  groupsMembers: 'Members',
  groupsPendingInvites: 'Pending invites',
  groupsDebts: 'Group debts',
  groupsOwner: 'Owner',
  groupsMemberCount: 'Members',
  groupsNoGroupOption: 'No group (private)',
  groupsSelectorLabel: 'Group (optional)',
  settingsGroupsFeature: 'Groups feature',
  settingsGroupsFeatureHint: 'Show Groups in the main navigation. Disabling does not delete your memberships.',
  errorNotPlatformUser: 'No platform user matches that email or phone. Ask them to sign up first.',
  errorAlreadyMember: 'This user is already a member or has a pending invitation.',
  errorInviteToSelf: 'You cannot invite yourself.',
  errorGroupFull: 'Group is full (max 20 members).',
  errorOwnerCannotLeave: 'Owner must transfer ownership before leaving.',
  errorNotAGroupMember: 'You are not an accepted member of this group.',
  errorNotGroupOwner: 'Only the group owner can perform this action.',
  errorGroupHasDebts: 'Cannot delete a group while debts are attached.',
  errorGroupTagLocked: 'Group tag cannot be changed once the debtor has accepted.',
  errorNotInSharedGroup: 'Both parties must be accepted members of the chosen group.',
  errorSameOwner: 'This person is already the owner.',
  errorNoPendingInvite: 'No pending invitation found.',
  errorIdentifierAmbiguous: 'Provide exactly one: user ID, email, or phone.',
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
  pendingConfirmation: 'Pending confirmation',
  editRequested: 'Edit requested',
  paymentPendingConfirmation: 'Payment pending confirmation',
  cancelled: 'Cancelled',
  checkEmail: 'Check Your Email',
  emailVerification: 'Email Verification',
  emailVerificationDesc: 'A verification link has been sent to your email. Please check your inbox to activate your account.',
  backToSignIn: 'Back to Sign In',
  creditorDashboard: 'Creditor Dashboard',
  debtorDashboard: 'Debtor Dashboard',
  dueSoon: 'Due Soon',
  debtors: 'Debtors',
  overdueAlerts: 'Overdue alerts',
  recentDebts: 'Recent Debts',
  allStatuses: 'All Statuses',
  noDebtsYet: 'No debts yet',
  noNotificationsYet: 'No notifications yet',
  errorGeneric: 'Something went wrong, please try again.',
  errorLoadDebts: "Couldn't load your debts. Please retry.",
  errorLoadDashboard: "Couldn't load your dashboard. Please retry.",
  errorLoadNotifications: "Couldn't load your notifications. Please retry.",
  errorTransitionStateChanged: "This debt's status changed — please refresh.",
  errorTransitionForbidden: "You're not allowed to perform this action.",
  loading: 'Loading...',
  selectAccountType: 'Select Account Type',
  selectAccountTypeDesc: 'How will you use Thabetha?',
  shopOwner: 'Shop Owner',
  shopOwnerDesc: 'Manage customer debts, issue invoices, scan QR codes',
  customer: 'Customer',
  customerDesc: 'Track my debts and confirm payments',
  continueAction: 'Continue',
  back: 'Back',
  upgradeToAi: 'Upgrade to AI Plan',
  upgradeToAiDesc: 'Voice-to-debt entry, smart summaries, and customer recommendations.',
  upgradeNow: 'Upgrade Now',
  aiActive: 'AI Active',
  scanCustomerQr: 'Scan Customer QR',
  scanCustomerQrDesc: "Enter a customer's QR token to open their profile and create a debt.",
  enterToken: 'Enter token',
  lookup: 'Lookup',
  customerProfile: 'Customer Profile',
  unpaidDebts: 'Unpaid Debts',
  myDebtStatus: 'My Debt Status',
  landingHeadline: 'A digital debt notebook both sides confirm',
  landingPitch: 'Replace the paper debt notebook with a simple, Arabic-first ledger that the creditor and debtor both confirm — with an internal commitment indicator and automatic reminders.',
  getStarted: 'Get started',
  learnMore: 'Learn more',
  forCreditors: 'For creditors',
  forDebtors: 'For debtors',
  creditorPitch: 'Create debts, scan a customer QR, confirm receipt of payments, and track receivables and overdue alerts.',
  debtorPitch: 'See every debt in one place, accept or request an edit, and notify the creditor when you pay.',
  receiptUpload: 'Debt receipts',
  receiptUploadHint: 'Attach images or PDFs up to 5 MB each',
  receiptAdd: 'Add receipt',
  receiptRemove: 'Remove',
  receiptRetry: 'Retry',
  receiptOpen: 'Open',
  receiptList: 'Receipts',
  receiptNone: 'No receipts',
  receiptLoading: 'Loading receipts...',
  receiptLoadFailed: 'Could not load receipts',
  receiptUploadFailed: 'Some receipts failed to upload. Retry them from the debt card.',
  receiptUploadRetry: 'Retry failed receipt uploads',
  receiptUploading: 'Uploading',
  receiptUploaded: 'Uploaded',
  receiptTooLarge: 'File limit is 5 MB',
  receiptUnsupported: 'Upload an image or PDF only',
  receiptLargeWarning: 'Large file, upload may take longer',
  receiptArchived: 'Archived',
  receiptAvailable: 'Available',
  qrExpiredAskRefresh: 'QR code expired — ask the customer to refresh their code',
  cannotBillSelf: "You can't bill yourself",
  clearDebtor: 'Change debtor',
  scannedDebtorLabel: 'Verified via QR',
  createDebtForPerson: 'Create debt for this person',
  languageLabel: 'Language',
  switchLanguage: 'العربية',
  navMenu: 'Menu',
  debtTrackerSubtitle: 'Debt Tracker',
  toastEditRequestSent: 'Edit request sent',
  toastDebtAccepted: 'Debt accepted',
  toastEditApproved: 'Edit approved',
  originalTermsStand: 'Original terms stand',
  toastEditRejected: 'Edit rejected',
  toastDebtCreated: 'Debt created',
  toastReceiptUploaded: 'Receipt uploaded',
  rescan: 'Rescan',
  debtorIdPlaceholder: 'Debtor user ID (optional)',
  toastPaymentRequested: 'Payment requested',
  toastPaymentConfirmed: 'Payment confirmed',
  toastProfileSaved: 'Profile saved',
  inbucketDevHint: '📧 Check Inbucket at localhost:55324',
  phonePlaceholder: '+966500000000',
  reminderDatePlaceholder: 'YYYY-MM-DD, YYYY-MM-DD',
  whatsapp_status_attempted: 'WhatsApp sent — awaiting confirmation',
  whatsapp_status_delivered: 'WhatsApp delivered',
  whatsapp_status_failed: 'WhatsApp failed',
  whatsapp_failed_reason_recipient_blocked: 'Recipient blocked the sender',
  whatsapp_failed_reason_invalid_phone: 'Invalid phone number',
  whatsapp_failed_reason_template_not_approved: 'Template not approved',
  whatsapp_failed_reason_template_param_mismatch: 'Template parameters did not match',
  whatsapp_failed_reason_provider_4xx: 'Rejected by WhatsApp',
  whatsapp_failed_reason_provider_5xx: 'Send failed — retry later',
  whatsapp_failed_reason_network_error: 'Network error',
  whatsapp_failed_reason_no_template: 'No template for this notification',
  whatsapp_failed_reason_no_phone_number: 'Recipient has no phone number',
  payOnline: 'Pay online',
  creditorReceives: 'Creditor receives',
  paymentProcessing: 'Processing payment...',
  paymentInProgress: 'A payment is already in progress — please wait.',
  paymentFailed: 'Payment failed — you can try again.',
  paymentSucceeded: 'Payment successful!',
  gatewayUnavailable: 'Payment gateway is unavailable, please try again later.',
  paymentPendingTitle: 'Payment processing',
  paymentPendingBody: "Payment not confirmed yet — status will update automatically when confirmation arrives.",
  feeLabel: 'Gateway fee',
  grossAmount: 'Gross amount',
  // Phase 9 — group settlement / auto-netting
  settlementCtaSettleGroup: 'Settle group',
  settlementCtaNothingToSettle: 'No active debts to settle.',
  settlementStatusOpen: 'Open',
  settlementStatusRejected: 'Rejected',
  settlementStatusExpired: 'Expired',
  settlementStatusSettled: 'Settled',
  settlementStatusFailed: 'Settlement failed',
  settlementRolePayer: 'Payer',
  settlementRoleReceiver: 'Receiver',
  settlementRoleObserver: 'Observer',
  settlementConfirm: 'Confirm',
  settlementReject: 'Reject',
  settlementExpiresIn: 'Expires in',
  settlementTransfersHeading: 'Proposed transfers',
  settlementProposedTitle: 'Settlement proposal',
  settlementReviewTitle: 'Review settlement',
  settlementCtaTryAgain: 'Try again',
  errorOpenProposalExists: 'A settlement proposal is already open for this group.',
  errorMixedCurrency: 'Mixed-currency debts cannot be auto-netted.',
  errorNothingToSettle: 'There is nothing to settle in this group.',
  errorNotARequiredParty: 'You are not a required party for this proposal.',
  errorAlreadyResponded: 'You have already responded to this proposal.',
  errorProposalNotOpen: 'The proposal is no longer open.',
  errorStaleSnapshot: 'A debt in the snapshot changed state — please retry.',
  errorLeaveBlockedByOpenProposal: 'You cannot leave while you are part of an open settlement proposal.',
};

const translations: Record<Language, Translations> = { ar, en };

/** Return the translated string for the given language and key. */
export function t(language: Language, key: TranslationKey): string {
  return translations[language]?.[key] ?? key;
}

/** @internal — exposed for key-parity tests only. */
export function _getTranslationKeys(locale: Language): string[] {
  return Object.keys(translations[locale]);
}

/** Format a date value using the active locale. Gregorian calendar only. */
export function formatDate(value: string | Date, locale: Language): string {
  const d = typeof value === 'string' ? new Date(value) : value;
  if (isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar-SA' : 'en-SA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    calendar: 'gregory',
  }).format(d);
}

/** Format a SAR (or other) currency amount using the active locale. */
export function formatCurrency(amount: number | string, locale: Language, currency = 'SAR'): string {
  const n = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(n)) return String(amount);
  return new Intl.NumberFormat(locale === 'ar' ? 'ar-SA' : 'en-SA', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}
