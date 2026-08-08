import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { PERMISSIONS } from '../constants/permissions'
import LeadListView from '../views/leads/LeadListView.vue'

const P = PERMISSIONS

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/AppLayout.vue'),
      children: [
        { path: '', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
        {
          path: 'upload',
          name: 'upload',
          component: () => import('../views/upload/UploadView.vue'),
          meta: { permissions: [P.materialsWrite] },
        },
        {
          path: 'materials',
          name: 'materials',
          component: () => import('../views/materials/MaterialListView.vue'),
          meta: { permissions: [P.materialsRead] },
        },
        {
          path: 'materials/:id',
          name: 'material-detail',
          component: () => import('../views/materials/MaterialDetailView.vue'),
          meta: { permissions: [P.materialsRead] },
        },
        {
          path: 'copies',
          name: 'copies',
          component: () => import('../views/copies/CopyListView.vue'),
          meta: { permissions: [P.copiesUse] },
        },
        {
          path: 'copies/generate',
          name: 'copies-generate',
          component: () => import('../views/copies/CopyGenerateView.vue'),
          meta: { permissions: [P.copiesUse] },
        },
        {
          path: 'copies/:id',
          name: 'copy-detail',
          component: () => import('../views/copies/CopyDetailView.vue'),
          meta: { permissions: [P.copiesUse] },
        },
        {
          path: 'posters',
          name: 'posters',
          component: () => import('../views/posters/PosterListView.vue'),
          meta: { permissions: [P.postersUse] },
        },
        {
          path: 'posters/generate',
          name: 'posters-generate',
          component: () => import('../views/posters/PosterGenerateView.vue'),
          meta: { permissions: [P.postersUse] },
        },
        {
          path: 'ai-image',
          name: 'ai-image',
          component: () => import('../views/ai/GptImagePlaygroundView.vue'),
          meta: { permissions: [P.aiImageUse] },
        },
        {
          path: 'leads',
          name: 'leads',
          component: LeadListView,
          meta: { permissions: [P.leadsRead] },
        },
        {
          path: 'leads/:id',
          name: 'lead-detail',
          component: () => import('../views/leads/LeadDetailView.vue'),
          meta: { permissions: [P.leadsRead] },
        },
        {
          path: 'students',
          name: 'students',
          component: () => import('../views/students/StudentListView.vue'),
          meta: { permissions: [P.studentsRead] },
        },
        {
          path: 'students/:id',
          name: 'student-detail',
          component: () => import('../views/students/StudentDetailView.vue'),
          meta: { permissions: [P.studentsRead] },
        },
        {
          path: 'enrollments',
          name: 'enrollments',
          component: () => import('../views/enrollments/EnrollmentView.vue'),
          meta: { permissions: [P.enrollmentsManage] },
        },
        {
          path: 'enrollments/records',
          name: 'enrollment-records',
          component: () => import('../views/enrollments/EnrollmentListView.vue'),
          meta: { permissions: [P.enrollmentsManage] },
        },
        {
          path: 'learning',
          name: 'learning',
          component: () => import('../views/learning/LearningListView.vue'),
          meta: { permissions: [P.learningWrite, P.studentsRead] },
        },
        {
          path: 'learning/new',
          name: 'learning-new',
          component: () => import('../views/learning/LearningNewView.vue'),
          meta: { permissions: [P.learningWrite] },
        },
        // ── 教务中心 ──
        {
          path: 'academic/classes',
          name: 'academic-classes',
          component: () => import('../views/academic/ClassListView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/classes/:id',
          name: 'academic-class-detail',
          component: () => import('../views/academic/ClassDetailView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/schedule',
          name: 'academic-schedule',
          component: () => import('../views/academic/ScheduleView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/class-records',
          name: 'academic-class-records',
          component: () => import('../views/academic/ClassRecordView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/class-records/:id',
          name: 'academic-class-record-detail',
          component: () => import('../views/academic/ClassRecordDetailView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/courses',
          name: 'academic-courses',
          component: () => import('../views/academic/CourseListView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        {
          path: 'academic/courses/new',
          name: 'academic-courses-new',
          component: () => import('../views/academic/CourseFormView.vue'),
          meta: { permissions: [P.academicCoursesAdmin] },
        },
        {
          path: 'academic/courses/:id/edit',
          name: 'academic-courses-edit',
          component: () => import('../views/academic/CourseFormView.vue'),
          meta: { permissions: [P.academicCoursesAdmin] },
        },
        {
          path: 'academic/teachers',
          name: 'academic-teachers',
          component: () => import('../views/academic/TeacherListView.vue'),
          meta: { permissions: [P.academicRead] },
        },
        // ── 财务中心 ──
        {
          path: 'finance/orders',
          name: 'finance-orders',
          component: () => import('../views/finance/OrderListView.vue'),
          meta: { permissions: [P.financeRead] },
        },
        {
          path: 'finance/orders/:id',
          name: 'finance-order-detail',
          component: () => import('../views/finance/OrderDetailView.vue'),
          meta: { permissions: [P.financeRead] },
        },
        {
          path: 'finance/transactions',
          name: 'finance-transactions',
          component: () => import('../views/finance/TransactionListView.vue'),
          meta: { permissions: [P.financeRead] },
        },
        {
          path: 'finance/consumption',
          name: 'finance-consumption',
          component: () => import('../views/finance/ConsumptionListView.vue'),
          meta: { permissions: [P.financeRead] },
        },
        {
          path: 'finance/recharge',
          name: 'finance-recharge',
          component: () => import('../views/finance/RechargeView.vue'),
          meta: { permissions: [P.financeRead] },
        },
        {
          path: 'finance/income-report',
          name: 'finance-income-report',
          component: () => import('../views/finance/IncomeReportView.vue'),
          meta: { permissions: [P.financeIncomeReport] },
        },
        {
          path: 'knowledge',
          redirect: '/knowledge/scripts',
        },
        {
          path: 'knowledge/:section',
          name: 'knowledge',
          component: () => import('../views/knowledge/KnowledgeView.vue'),
          meta: { permissions: [P.knowledgeRead] },
        },
        {
          path: 'templates',
          name: 'templates',
          component: () => import('../views/templates/TemplateViews.vue'),
          meta: { permissions: [P.templatesManage] },
        },
        {
          path: 'templates/copies/:id',
          name: 'copy-template-detail',
          component: () => import('../views/templates/TemplateDetailView.vue'),
          meta: { permissions: [P.templatesManage], templateKind: 'copies' },
        },
        {
          path: 'templates/posters/:id',
          name: 'poster-template-detail',
          component: () => import('../views/templates/TemplateDetailView.vue'),
          meta: { permissions: [P.templatesManage], templateKind: 'posters' },
        },
        {
          path: 'office',
          name: 'office',
          component: () => import('../views/office/OfficeSheetsView.vue'),
          meta: { permissions: [P.officeUse] },
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('../views/users/UserListView.vue'),
          meta: { permissions: [P.usersManage] },
        },
        {
          path: 'more',
          name: 'app-more',
          component: () => import('../views/MoreView.vue'),
          // 登录即可：页面内按权限过滤入口
          meta: {},
        },
      ],
    },
    // 旧 /m 书签 → 统一正式路径（不再挂 MobileLayout）
    { path: '/m', redirect: '/' },
    { path: '/m/upload', redirect: '/upload' },
    { path: '/m/materials', redirect: '/materials' },
    { path: '/m/students', redirect: '/students' },
    {
      path: '/m/students/:id',
      redirect: (to) => `/students/${to.params.id}`,
    },
    { path: '/m/learning', redirect: '/learning' },
    { path: '/m/learning/new', redirect: '/learning/new' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (auth.isLoggedIn && to.name === 'login') {
      return '/'
    }
    return true
  }

  if (!auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    try {
      await auth.loadMe()
    } catch {
      auth.logout()
      return { name: 'login' }
    }
  }

  const perms = to.meta.permissions as string[] | undefined
  if (perms?.length && !auth.hasAnyPermission(...perms)) {
    return '/'
  }

  // Legacy role meta (if any remaining)
  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role) && !perms?.length) {
    return '/'
  }

  return true
})

export default router
