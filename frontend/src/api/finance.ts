import client from './client'
import { asPageResult, type PageResult } from './paging'

export interface OrderLineItem {
  course_id?: number | null
  name: string
  tag: string
  type?: string
  price_label: string
  quantity_label: string
  hours?: number
  unit_price?: number
  total: number
  gift_qty: string
  leave_free: string
  discount: number
  subtotal: number
  coupon: string
  receivable: number
  class_name: string
  valid_until: string
}

export interface FinanceTransaction {
  id: number
  handled_at?: string
  item: string
  type: string
  tx_type: string
  status: string
  status_code: string
  amount: number
  pay_method: string
  account: string
  handler: string
  order_id?: number | null
  order_no: string
  student_id?: number | null
  payer: string
  voucher: string
  flow_no: string
  remark: string
  created_at?: string
}

export interface FinanceOrder {
  id: number
  order_no: string
  student_id: number
  student: string
  phone: string
  order_type: string
  order_type_label: string
  item: string
  item_summary: string
  courses: { id?: number; name?: string; type?: string; price_label?: string; hours?: number; unit_price?: number }[]
  receivable: number
  received: number
  arrears: number
  status: string
  status_label: string
  source: string
  performance_owner: string
  handler: string
  pay_method: string
  handled_at?: string | null
  paid_at?: string | null
  creator: string
  created_at?: string
}

export interface FinanceOrderDetail extends FinanceOrder {
  student_grade?: string
  student_school?: string
  parent_name?: string
  gender?: string
  internal_notes?: string
  external_notes?: string
  line_items: OrderLineItem[]
  line_receivable_sum: number
  payments: FinanceTransaction[]
  performance_owner_id?: number | null
  handler_id?: number | null
  enrollment_id?: number | null
}

export interface TransactionListResult extends PageResult<FinanceTransaction> {
  summary?: {
    income: number
    pending_income: number
    expense: number
    pending_expense: number
  }
}

export interface CourseConsumption {
  id: number
  consumed_at?: string
  student_id: number
  student: string
  student_phone?: string
  student_grade?: string
  class_id?: number | null
  class_name: string
  course_id?: number | null
  course_name: string
  course_type?: string
  course_type_label?: string
  course_grade?: string
  subject?: string
  term?: string
  teacher: string
  teacher_id?: number | null
  /** 该课次全部上课老师 id（与点名/排课一致） */
  teacher_ids?: number[]
  record_id?: number | null
  consume_type: string
  source: string
  hours: number
  hours_label: string
  uncovered_hours: number
  amount: number
  status: string
  status_label?: string
  created_at?: string
}

export interface CourseConsumptionOrder {
  package_id?: number | null
  order_id?: number | null
  order_no: string
  course_name: string
  unit_price: number
  hours: number
  gift_hours: number
  amount: number
}

export interface CourseConsumptionDetail extends CourseConsumption {
  class_start?: string | null
  class_end?: string | null
  roll_at?: string | null
  attendance_status?: string
  attendance_status_label?: string
  operator?: string
  operation_time?: string | null
  orders: CourseConsumptionOrder[]
}

export interface ConsumptionListResult extends PageResult<CourseConsumption> {
  summary?: { amount: number }
}

export interface RechargeRecord {
  id: number
  student_id: number
  student: string
  phone: string
  amount: number
  balance: number
  pay_method: string
  handler: string
  status: string
  remark: string
  created_at?: string
}

export interface IncomeReport {
  pending_income: number
  confirmed_income: number
  total_income: number
  by_pay_method: { method: string; count: number; amount: number }[]
  income_chart?: { date: string; pending: number; confirmed: number; total: number }[]
  course_consumption?: {
    total_hours: number
    total_amount: number
    total_count: number
    chart?: { date: string; hours: number; amount: number; count: number }[]
    by_course: {
      course_name: string
      course_type?: string
      course_type_label?: string
      count: number
      hours: number
      amount: number
    }[]
  }
}

export interface PendingHoursMetrics {
  package_count: number
  purchased_hours: number
  gift_hours: number
  total_hours: number
  consumed_hours: number
  pending_hours: number
  pending_value: number
  expired_hours: number
  expiring_soon_hours: number
  consumption_rate: number
  risk_status: 'expired' | 'expiring' | 'normal' | 'consumed'
}

export interface PendingHoursSummary extends PendingHoursMetrics {
  student_count: number
  pending_student_count: number
}

export interface PendingHoursCourse extends PendingHoursMetrics {
  course_id: number
  course_name: string
  course_type: string
  course_type_label: string
  student_count: number
}

export interface PendingHoursItem extends PendingHoursMetrics {
  student_id: number
  student_name: string
  student_phone: string
  student_grade: string
  student_status: string
  course_id: number
  course_name: string
  course_type: string
  course_type_label: string
  valid_until?: string | null
}

export interface PendingHoursReport {
  as_of: string
  summary: PendingHoursSummary
  by_course: PendingHoursCourse[]
  items: PendingHoursItem[]
}

export async function listOrdersApi(params: {
  order_no?: string
  student_q?: string
  order_type?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<FinanceOrder>> {
  const res = await client.get('/finance/orders', { params })
  return asPageResult<FinanceOrder>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function createOrderApi(payload: {
  student_id: number
  order_type?: string
  item_summary?: string
  receivable?: number
  received?: number
  pay_method?: string
  handled_at?: string | null
  performance_owner_id?: number | null
}): Promise<FinanceOrder> {
  const res = await client.post('/finance/orders', payload)
  return res.data.data
}

export async function getOrderDetailApi(
  orderId: number,
  opts?: { logView?: boolean },
): Promise<FinanceOrderDetail> {
  const res = await client.get(`/finance/orders/${orderId}`, {
    params: opts?.logView ? { log_view: true } : undefined,
  })
  return res.data.data
}

export async function voidOrderApi(orderId: number): Promise<FinanceOrderDetail> {
  const res = await client.post(`/finance/orders/${orderId}/void`)
  return res.data.data
}

export interface OrderOperationLog {
  id: number
  order_id: number
  action: string
  action_label: string
  detail: string
  operator_id?: number | null
  operator_name: string
  created_at?: string
}

export async function listOrderLogsApi(
  orderId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<{ items: OrderOperationLog[]; total: number; page?: number; page_size?: number }> {
  const res = await client.get(`/finance/orders/${orderId}/logs`, {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  })
  return res.data.data
}

/** 下载订单收据 PDF */
export async function downloadOrderReceiptApi(
  orderId: number,
  meta?: { orderNo?: string; studentName?: string },
): Promise<void> {
  const res = await client.get(`/finance/orders/${orderId}/receipt`, {
    responseType: 'blob',
    timeout: 60_000,
  })
  const blob = res.data as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const student = (meta?.studentName || '学员').replace(/[\\/:*?"<>|]/g, '-').trim() || '学员'
  const no = (meta?.orderNo || String(orderId)).replace(/[\\/:*?"<>|]/g, '-').trim()
  a.download = `收据_${student}_${no}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function listTransactionsApi(params: {
  item?: string
  tx_type?: string
  status?: string
  include_void?: boolean
  page?: number
  page_size?: number
} = {}): Promise<TransactionListResult> {
  const res = await client.get('/finance/transactions', { params })
  const data = res.data.data || {}
  const page = asPageResult<FinanceTransaction>(data, params.page ?? 1, params.page_size ?? 20)
  return { ...page, summary: data.summary }
}

export async function confirmTransactionsApi(ids: number[]): Promise<{ confirmed: number }> {
  const res = await client.post('/finance/transactions/confirm', { ids })
  return res.data.data
}

export async function voidTransactionApi(id: number): Promise<FinanceTransaction> {
  const res = await client.post(`/finance/transactions/${id}/void`)
  return res.data.data
}

export async function listConsumptionsApi(params: {
  student_q?: string
  class_id?: number
  course_id?: number
  course_type?: string
  teacher_id?: number
  consume_type?: string
  source?: string
  status?: string
  hide_void?: boolean
  start_date?: string
  end_date?: string
  grade?: string
  subject?: string
  term?: string
  page?: number
  page_size?: number
} = {}): Promise<ConsumptionListResult> {
  const res = await client.get('/finance/consumptions', { params })
  const data = res.data.data || {}
  const page = asPageResult<CourseConsumption>(data, params.page ?? 1, params.page_size ?? 20)
  return { ...page, summary: data.summary }
}

export async function getConsumptionDetailApi(id: number): Promise<CourseConsumptionDetail> {
  const res = await client.get(`/finance/consumptions/${id}`)
  return res.data.data
}

export async function listRechargesApi(params: {
  student_q?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<RechargeRecord>> {
  const res = await client.get('/finance/recharges', { params })
  return asPageResult<RechargeRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function createRechargeApi(payload: {
  student_id: number
  amount: number
  pay_method?: string
  remark?: string
}): Promise<RechargeRecord> {
  const res = await client.post('/finance/recharges', payload)
  return res.data.data
}

export async function getIncomeReportApi(params: {
  start_date?: string
  end_date?: string
} = {}): Promise<IncomeReport> {
  const res = await client.get('/finance/income-report', { params })
  return res.data.data
}

export async function getPendingHoursReportApi(): Promise<PendingHoursReport> {
  const res = await client.get('/finance/pending-hours-report')
  return res.data.data
}
