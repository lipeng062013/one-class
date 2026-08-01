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
          path: 'upload',
          name: 'upload',
          component: () => import('../views/upload/UploadView.vue'),
          meta: { roles: ['admin', 'operator', 'teacher'] },
        },
        {
          path: 'materials',
          name: 'materials',
          component: () => import('../views/materials/MaterialListView.vue'),
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
          meta: { roles: ['admin', 'teacher'] },
        },
        {
          path: 'students/:id',
          name: 'student-detail',
          component: () => import('../views/students/StudentDetailView.vue'),
          meta: { roles: ['admin', 'teacher'] },
        },
        {
          path: 'learning',
          name: 'learning',
          component: () => import('../views/learning/LearningListView.vue'),
          meta: { roles: ['admin', 'teacher'] },
        },
        {
          path: 'learning/new',
          name: 'learning-new',
          component: () => import('../views/learning/LearningNewView.vue'),
          meta: { roles: ['admin', 'teacher'] },
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

  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) {
    return '/'
  }

  return true
})

export default router
