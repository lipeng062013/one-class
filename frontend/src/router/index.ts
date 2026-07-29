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
        {
          path: '',
          name: 'dashboard',
          component: () => import('../views/DashboardView.vue'),
        },
        {
          path: 'materials',
          name: 'materials',
          component: () => import('../views/materials/MaterialListView.vue'),
          meta: { roles: ['admin', 'operator'] },
        },
        {
          path: 'materials/:id',
          name: 'material-detail',
          component: () => import('../views/materials/MaterialDetailView.vue'),
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

  if (auth.isTeacher && !to.path.startsWith('/m/')) {
    return '/m/upload'
  }

  if (!auth.isTeacher && to.path.startsWith('/m/')) {
    return '/'
  }

  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) {
    return '/'
  }

  return true
})

export default router
