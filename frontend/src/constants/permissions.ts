/** Permission codes — keep in sync with backend/app/core/permissions.py */

export const PERMISSIONS = {
  usersManage: 'users.manage',
  dashboardRead: 'dashboard.read',
  systemRead: 'system.read',
  materialsRead: 'materials.read',
  materialsWrite: 'materials.write',
  materialsManage: 'materials.manage',
  copiesUse: 'copies.use',
  postersUse: 'posters.use',
  aiImageUse: 'ai_image.use',
  knowledgeRead: 'knowledge.read',
  knowledgeWrite: 'knowledge.write',
  templatesManage: 'templates.manage',
  officeUse: 'office.use',
  leadsRead: 'leads.read',
  leadsWrite: 'leads.write',
  studentsRead: 'students.read',
  studentsWrite: 'students.write',
  studentsDelete: 'students.delete',
  learningWrite: 'learning.write',
  academicRead: 'academic.read',
  academicWrite: 'academic.write',
  academicCoursesAdmin: 'academic.courses_admin',
  financeRead: 'finance.read',
  financeWrite: 'finance.write',
  financeIncomeReport: 'finance.income_report',
  enrollmentsManage: 'enrollments.manage',
} as const

export type PermissionCode = (typeof PERMISSIONS)[keyof typeof PERMISSIONS]
