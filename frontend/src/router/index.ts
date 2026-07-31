import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

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
          path: 'materials',
          name: 'materials',
          component: () => import('../views/materials/MaterialListView.vue'),
          // 负责人 / 运营 / 老师均可上传与查看素材
          meta: { roles: ['admin', 'operator', 'teacher'] },
        },
        {
          path: 'materials/:id',
          name: 'material-detail',
          component: () => import('../views/materials/MaterialDetailView.vue'),
          meta: { roles: ['admin', 'operator', 'teacher'] },
        },
        {
          path: 'copies',
          name: 'copies',
          component: () => import('../views/copies/CopyListView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'copies/generate',
          name: 'copies-generate',
          component: () => import('../views/copies/CopyGenerateView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'copies/:id',
          name: 'copy-detail',
          component: () => import('../views/copies/CopyDetailView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'posters',
          name: 'posters',
          component: () => import('../views/posters/PosterListView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'posters/generate',
          name: 'posters-generate',
          component: () => import('../views/posters/PosterGenerateView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'ai-image',
          name: 'ai-image',
          component: () => import('../views/ai/GptImagePlaygroundView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'leads',
          name: 'leads',
          component: () => import('../views/leads/LeadListView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'students',
          name: 'students',
          component: () => import('../views/students/StudentListView.vue'),
          meta: { roles: ['admin'] },
        },
        {
          path: 'students/:id',
          name: 'student-detail',
          component: () => import('../views/students/StudentDetailView.vue'),
          meta: { roles: ['admin'] },
        },
        {
          path: 'knowledge',
          redirect: '/knowledge/scripts',
        },
        {
          path: 'knowledge/:section',
          name: 'knowledge',
          component: () => import('../views/knowledge/KnowledgeView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'templates',
          name: 'templates',
          component: () => import('../views/templates/TemplateViews.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'templates/copies/:id',
          name: 'copy-template-detail',
          component: () => import('../views/templates/TemplateDetailView.vue'),
          meta: { roles: ['admin', 'operator'], templateKind: 'copies' },
        },
        {
          path: 'templates/posters/:id',
          name: 'poster-template-detail',
          component: () => import('../views/templates/TemplateDetailView.vue'),
          meta: { roles: ['admin', 'operator'], templateKind: 'posters' },
        },
        {
          path: 'office',
          name: 'office',
          component: () => import('../views/office/OfficeSheetsView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('../views/users/UserListView.vue'),
          meta: { roles: ['admin'] },
        },
      ],
    },
    {
      path: '/m',
      component: () => import('../layouts/MobileLayout.vue'),
      children: [
        {
          path: 'upload',
          name: 'mobile-upload',
          component: () => import('../views/mobile/MobileUploadView.vue'),
        },
        {
          path: 'materials',
          name: 'mobile-materials',
          component: () => import('../views/mobile/MobileMaterialsView.vue'),
        },
        {
          path: 'students',
          name: 'mobile-students',
          component: () => import('../views/mobile/MobileStudentsView.vue'),
        },
        {
          path: 'students/:id',
          name: 'mobile-student-detail',
          component: () => import('../views/mobile/MobileStudentDetailView.vue'),
        },
        {
          path: 'learning',
          name: 'mobile-learning',
          component: () => import('../views/mobile/MobileLearningView.vue'),
        },
        {
          path: 'learning/new',
          name: 'mobile-learning-new',
          component: () => import('../views/mobile/MobileLearningNewView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (auth.isLoggedIn && to.name === 'login') {
      return auth.isTeacher ? '/m/upload' : '/'
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

  // 老师默认手机端；工作台与素材（上传/管理）允许访问桌面
  const teacherDesktopAllowed =
    to.path === '/' || to.path === '/materials' || to.path.startsWith('/materials/')
  if (auth.isTeacher && !to.path.startsWith('/m/') && !teacherDesktopAllowed) {
    return '/m/upload'
  }

  // 负责人、运营也可使用手机端「上传素材」
  // （仅拦截老师以外用户进入除 upload/materials 外的手机页）
  if (!auth.isTeacher && to.path.startsWith('/m/')) {
    const opsMobileAllowed =
      to.path === '/m/upload' ||
      to.path === '/m/materials' ||
      to.path.startsWith('/m/materials/')
    if (!opsMobileAllowed) {
      return '/'
    }
  }

  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) {
    return '/'
  }

  return true
})

export default router
