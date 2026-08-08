import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

export type MenuItem = { index: string; title: string; icon: string }
export type MenuGroup = {
  type: 'group'
  index: string
  title: string
  icon: string
  children: MenuItem[]
}
export type MenuEntry = (MenuItem & { type?: 'item' }) | MenuGroup

const roleLabel: Record<string, string> = {
  admin: '负责人',
  operator: '运营',
  teacher: '老师',
  cr: 'CR（班主任，学管师）',
  academic_manager: 'CR（班主任，学管师）',
}

/** 侧栏 / 更多页共用的权限菜单 */
export function useAppMenus() {
  const auth = useAuthStore()

  const displayName = computed(
    () => auth.user?.display_name || auth.user?.username || '用户',
  )

  const roleText = computed(
    () => roleLabel[auth.user?.role || ''] || auth.user?.role || '',
  )

  const brandTag = computed(() => (auth.isTeacher ? '老师端后台' : '管理后台'))

  const menus = computed((): MenuEntry[] => {
    const can = (code: string) => auth.hasPermission(code)

    const hasOpsExtras =
      can('copies.use') ||
      can('posters.use') ||
      can('ai_image.use') ||
      can('knowledge.read') ||
      can('leads.read') ||
      can('finance.read') ||
      can('enrollments.manage') ||
      can('academic.write') ||
      can('users.manage')

    if (auth.isTeacher && !hasOpsExtras) {
      // 精简老师端：上传入口在素材页内，侧栏只保留「素材」
      return [
        { index: '/', title: '工作台', icon: 'Odometer' },
        ...(can('materials.read') || can('materials.write')
          ? [{ index: '/materials', title: '素材', icon: 'Picture' }]
          : []),
        ...(can('students.read') ? [{ index: '/students', title: '学员', icon: 'Avatar' }] : []),
        ...(can('academic.read')
          ? [{ index: '/academic/schedule', title: '我的课表', icon: 'Calendar' }]
          : []),
        ...(can('learning.write') ? [{ index: '/learning', title: '上传学情', icon: 'EditPen' }] : []),
      ]
    }

    const items: MenuEntry[] = [{ index: '/', title: '工作台', icon: 'Odometer' }]

    // 获客中心
    if (can('leads.read')) {
      items.push({
        type: 'group',
        index: 'crm',
        title: '获客中心',
        icon: 'UserFilled',
        children: [{ index: '/leads', title: '线索跟进', icon: 'Phone' }],
      })
    }

    // 教务中心
    const academicChildren: MenuItem[] = []
    if (can('students.read')) {
      academicChildren.push({ index: '/students', title: '学员管理', icon: 'Avatar' })
    }
    if (can('academic.read')) {
      academicChildren.push(
        { index: '/academic/classes', title: '班级管理', icon: 'Collection' },
        { index: '/academic/schedule', title: '课表管理', icon: 'Calendar' },
        { index: '/academic/class-records', title: '上课记录', icon: 'Notebook' },
        { index: '/academic/courses', title: '课程管理', icon: 'Reading' },
        { index: '/academic/teachers', title: '老师管理', icon: 'User' },
      )
    }
    if (can('learning.write')) {
      academicChildren.push({ index: '/learning', title: '学情', icon: 'EditPen' })
    }
    if (academicChildren.length) {
      items.push({
        type: 'group',
        index: 'academic',
        title: '教务中心',
        icon: 'School',
        children: academicChildren,
      })
    }

    // 财务中心（教务之下、成长中心之上）
    const financeChildren: MenuItem[] = []
    if (can('finance.read')) {
      financeChildren.push({ index: '/finance/orders', title: '订单管理', icon: 'Tickets' })
    }
    if (can('enrollments.manage')) {
      financeChildren.push({ index: '/enrollments', title: '报名/续费', icon: 'Ticket' })
    }
    if (can('finance.read')) {
      // 运营仅开放订单 + 课消（数据已按本人范围收窄）；收支/充值为全量财务视角
      const isOperator = auth.user?.role === 'operator'
      if (!isOperator) {
        financeChildren.push({ index: '/finance/transactions', title: '收支明细', icon: 'List' })
      }
      financeChildren.push({ index: '/finance/consumption', title: '课消记录', icon: 'DataLine' })
      if (!isOperator) {
        financeChildren.push({ index: '/finance/recharge', title: '充值管理', icon: 'Coin' })
      }
    }
    if (can('finance.income_report')) {
      financeChildren.push({
        index: '/finance/income-report',
        title: '确认收入报表',
        icon: 'DataAnalysis',
      })
    }
    if (financeChildren.length) {
      items.push({
        type: 'group',
        index: 'finance',
        title: '财务中心',
        icon: 'Wallet',
        children: financeChildren,
      })
    }

    // 成长中心（财务中心之下、运营中心之上）
    if (can('knowledge.read')) {
      items.push({
        type: 'group',
        index: 'growth',
        title: '成长中心',
        icon: 'Reading',
        children: [
          { index: '/knowledge/scripts', title: '沟通话术', icon: 'ChatDotRound' },
          { index: '/knowledge/objections', title: '异议处理', icon: 'Comment' },
          { index: '/knowledge/banned', title: '禁用词列表', icon: 'Warning' },
        ],
      })
    }

    /**
     * 运营中心：素材 / 文案 / 海报 / GPT 生图
     * 顺序：成长中心之下
     * 「上传素材」入口在素材模块内（列表页 → /upload）
     */
    const opsChildren: MenuItem[] = []
    if (can('materials.read') || can('materials.write')) {
      opsChildren.push({ index: '/materials', title: '素材', icon: 'Picture' })
    }
    if (can('copies.use')) {
      opsChildren.push({ index: '/copies', title: '文案', icon: 'Document' })
    }
    if (can('posters.use')) {
      opsChildren.push({ index: '/posters', title: '海报', icon: 'PictureFilled' })
    }
    if (can('ai_image.use')) {
      opsChildren.push({ index: '/ai-image', title: 'GPT 生图', icon: 'MagicStick' })
    }
    if (opsChildren.length) {
      items.push({
        type: 'group',
        index: 'ops',
        title: '运营中心',
        icon: 'Promotion',
        children: opsChildren,
      })
    }
    if (can('templates.manage')) {
      items.push({ index: '/templates', title: '模板', icon: 'Files' })
    }
    if (can('office.use')) {
      items.push({ index: '/office', title: '综合办公表', icon: 'Grid' })
    }
    if (can('users.manage')) {
      items.push({ index: '/users', title: '用户管理', icon: 'User' })
    }
    return items
  })

  const flatMenuItems = computed<MenuItem[]>(() =>
    menus.value.flatMap((entry) => (entry.type === 'group' ? entry.children : [entry])),
  )

  return {
    auth,
    menus,
    flatMenuItems,
    displayName,
    roleText,
    brandTag,
  }
}
