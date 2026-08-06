/**
 * 工作台「快捷入口」可选目录。
 * 图标一律使用本站 Element Plus 图标名，不照搬外部产品 icon。
 */

export type QuickLinkDef = {
  /** 稳定 id，写入 localStorage */
  id: string
  title: string
  desc: string
  path: string
  icon: string
  /** 分组标题（自定义弹窗） */
  group: string
  /**
   * 进入该入口所需权限（任一即可）。
   * 未配置时按角色标记（adminOnly / teacherOnly 等）回退。
   */
  permissions?: string[]
  /** 仅负责人（无 permissions 时的回退） */
  adminOnly?: boolean
  /** 仅老师 */
  teacherOnly?: boolean
  /** 运营/负责人（非老师）— 无 permissions 时的回退 */
  opsOnly?: boolean
  /** 老师不可见（如点名由学管/负责人完成） */
  hideForTeacher?: boolean
  /** 默认是否选中 */
  defaultSelected?: boolean
  primary?: boolean
}

/** 全量目录（按权限过滤后使用） */
export const QUICK_LINK_CATALOG: QuickLinkDef[] = [
  // 学员与学情
  {
    id: 'students',
    title: '学生信息',
    desc: '学员档案',
    path: '/students',
    icon: 'Avatar',
    group: '学员与学情',
    permissions: ['students.read'],
    defaultSelected: true,
    primary: true,
  },
  {
    id: 'learning',
    title: '学情',
    desc: '记录与查看',
    path: '/learning',
    icon: 'EditPen',
    group: '学员与学情',
    permissions: ['learning.write', 'students.read'],
    defaultSelected: true,
  },
  {
    id: 'learning-new',
    title: '写学情',
    desc: '新建一条学情',
    path: '/learning/new',
    icon: 'Notebook',
    group: '学员与学情',
    permissions: ['learning.write'],
    teacherOnly: true,
    defaultSelected: true,
  },
  {
    id: 'enrollments',
    title: '报名/续费',
    desc: '办理报名续费',
    path: '/enrollments',
    icon: 'Ticket',
    group: '财务中心',
    permissions: ['enrollments.manage'],
    defaultSelected: true,
  },
  {
    id: 'academic-classes',
    title: '班级管理',
    desc: '班课 / 一对一',
    path: '/academic/classes',
    icon: 'Collection',
    group: '教务中心',
    permissions: ['academic.read'],
    defaultSelected: true,
  },
  {
    id: 'academic-schedule',
    title: '课表',
    desc: '我的上课安排',
    path: '/academic/schedule',
    icon: 'Calendar',
    group: '教务中心',
    permissions: ['academic.read'],
    defaultSelected: true,
    primary: true,
  },
  {
    id: 'academic-roll-call',
    title: '点名',
    desc: '周课表选课点名',
    path: '/academic/class-records?roll=1',
    icon: 'CircleCheck',
    group: '教务中心',
    permissions: ['academic.write'],
    defaultSelected: true,
    primary: true,
    // 点名由学管/负责人完成，老师不需要点名入口
    hideForTeacher: true,
  },
  {
    id: 'academic-class-records',
    title: '上课记录',
    desc: '点名与课消',
    path: '/academic/class-records',
    icon: 'Notebook',
    group: '教务中心',
    permissions: ['academic.read'],
  },
  {
    id: 'academic-courses',
    title: '课程管理',
    desc: '课程与定价',
    path: '/academic/courses',
    icon: 'Reading',
    group: '教务中心',
    permissions: ['academic.read'],
  },
  {
    id: 'finance-orders',
    title: '订单管理',
    desc: '报名转课退费',
    path: '/finance/orders',
    icon: 'Tickets',
    group: '财务中心',
    permissions: ['finance.read'],
    defaultSelected: true,
  },
  {
    id: 'finance-transactions',
    title: '收支明细',
    desc: '收入确认',
    path: '/finance/transactions',
    icon: 'List',
    group: '财务中心',
    permissions: ['finance.read'],
  },
  {
    id: 'finance-consumption',
    title: '课消记录',
    desc: '课时消耗',
    path: '/finance/consumption',
    icon: 'DataLine',
    group: '财务中心',
    permissions: ['finance.read'],
  },
  {
    id: 'leads',
    title: '线索跟进',
    desc: '跟进转化',
    path: '/leads',
    icon: 'Phone',
    group: '获客',
    permissions: ['leads.read'],
    defaultSelected: true,
  },
  // 内容
  {
    id: 'upload',
    title: '上传素材',
    desc: '课堂照片',
    path: '/upload',
    icon: 'Upload',
    group: '内容生产',
    permissions: ['materials.write'],
    defaultSelected: true,
  },
  {
    id: 'materials',
    title: '素材',
    desc: '上传与管理',
    path: '/materials',
    icon: 'Picture',
    group: '内容生产',
    permissions: ['materials.read'],
    defaultSelected: true,
    primary: true,
  },
  {
    id: 'copies',
    title: '文案',
    desc: '文案列表',
    path: '/copies',
    icon: 'Document',
    group: '内容生产',
    permissions: ['copies.use'],
  },
  {
    id: 'copies-generate',
    title: '生成文案',
    desc: '模板 / AI',
    path: '/copies/generate',
    icon: 'EditPen',
    group: '内容生产',
    permissions: ['copies.use'],
    defaultSelected: true,
  },
  {
    id: 'posters',
    title: '海报',
    desc: '海报列表',
    path: '/posters',
    icon: 'PictureFilled',
    group: '内容生产',
    permissions: ['posters.use'],
  },
  {
    id: 'posters-generate',
    title: '生成海报',
    desc: '版式 / 生图',
    path: '/posters/generate',
    icon: 'Brush',
    group: '内容生产',
    permissions: ['posters.use'],
    defaultSelected: true,
  },
  {
    id: 'ai-image',
    title: 'GPT 生图',
    desc: 'AI 出图',
    path: '/ai-image',
    icon: 'MagicStick',
    group: '内容生产',
    permissions: ['ai_image.use'],
  },
  // 成长与办公
  {
    id: 'knowledge',
    title: '成长中心',
    desc: '话术与异议',
    path: '/knowledge/scripts',
    icon: 'Reading',
    group: '成长与办公',
    permissions: ['knowledge.read'],
    defaultSelected: true,
  },
  {
    id: 'templates',
    title: '模板',
    desc: '文案/海报模板',
    path: '/templates',
    icon: 'Files',
    group: '成长与办公',
    permissions: ['templates.manage'],
  },
  {
    id: 'office',
    title: '综合办公',
    desc: '表格协作',
    path: '/office',
    icon: 'Grid',
    group: '成长与办公',
    permissions: ['office.use'],
    defaultSelected: true,
  },
  {
    id: 'users',
    title: '用户管理',
    desc: '账号权限',
    path: '/users',
    icon: 'User',
    group: '成长与办公',
    permissions: ['users.manage'],
    defaultSelected: true,
  },
]

const STORAGE_PREFIX = 'oc-quick-links-v1'
const QUICK_LINK_MIGRATIONS = [
  { version: 'roll-call-v1', id: 'academic-roll-call' },
] as const

export function quickLinksStorageKey(userId: number | string | null | undefined, role: string) {
  return `${STORAGE_PREFIX}:${userId ?? 'anon'}:${role || 'unknown'}`
}

export function filterCatalogForRole(opts: {
  isAdmin: boolean
  isTeacher: boolean
  /** 有效权限判断；传入后优先按 permissions 过滤（与侧栏一致） */
  hasPermission?: (code: string) => boolean
}): QuickLinkDef[] {
  const can = opts.hasPermission
  return QUICK_LINK_CATALOG.filter((item) => {
    if (item.hideForTeacher && opts.isTeacher) return false
    if (item.teacherOnly && !opts.isTeacher) return false

    if (can && item.permissions?.length) {
      return item.permissions.some((code) => can(code))
    }

    // 无 hasPermission / permissions 时的角色回退（兼容旧调用）
    if (item.adminOnly && !opts.isAdmin) return false
    if (item.opsOnly && opts.isTeacher) return false
    if (
      (item.id === 'students' ||
        item.id === 'learning' ||
        item.id.startsWith('academic-')) &&
      !opts.isAdmin &&
      !opts.isTeacher
    ) {
      return false
    }
    return true
  })
}

export function defaultSelectedIds(catalog: QuickLinkDef[]): string[] {
  return catalog.filter((c) => c.defaultSelected).map((c) => c.id)
}

/** 读取用户自定义顺序；无效则回退默认 */
export function loadQuickLinkIds(
  storageKey: string,
  catalog: QuickLinkDef[],
): string[] {
  const allowed = new Set(catalog.map((c) => c.id))
  try {
    const raw = localStorage.getItem(storageKey)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    let ids = Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === 'string' && allowed.has(x))
      : defaultSelectedIds(catalog)
    // 至少保留 1 个，否则回退默认
    if (!ids.length) ids = defaultSelectedIds(catalog)

    for (const migration of QUICK_LINK_MIGRATIONS) {
      const markerKey = `${storageKey}:migration:${migration.version}`
      if (localStorage.getItem(markerKey)) continue
      if (allowed.has(migration.id) && !ids.includes(migration.id)) {
        ids = [migration.id, ...ids]
        localStorage.setItem(storageKey, JSON.stringify(ids))
      }
      localStorage.setItem(markerKey, '1')
    }
    return ids
  } catch {
    return defaultSelectedIds(catalog)
  }
}

export function saveQuickLinkIds(storageKey: string, ids: string[]) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(ids))
  } catch {
    /* quota */
  }
}

export function resolveQuickLinks(
  ids: string[],
  catalog: QuickLinkDef[],
): QuickLinkDef[] {
  const map = new Map(catalog.map((c) => [c.id, c]))
  return ids.map((id) => map.get(id)).filter((x): x is QuickLinkDef => !!x)
}

export function groupCatalog(catalog: QuickLinkDef[]): { group: string; items: QuickLinkDef[] }[] {
  const order: string[] = []
  const buckets = new Map<string, QuickLinkDef[]>()
  for (const item of catalog) {
    if (!buckets.has(item.group)) {
      buckets.set(item.group, [])
      order.push(item.group)
    }
    buckets.get(item.group)!.push(item)
  }
  return order.map((group) => ({ group, items: buckets.get(group)! }))
}
