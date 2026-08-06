import client from './client'
import { asPageResult, type PageResult } from './paging'

export type EnrollmentKind = 'enroll' | 'renew'

export interface EnrollmentAttribution {
  user_id: number
  display_name: string
  amount: number
}

export interface EnrollmentCourse {
  id?: number | null
  name: string
  type?: string
  price_label?: string
  hours?: number
  unit_price?: number
  gift_hours?: number
  price_standard?: string
  discount_type?: 'reduce' | 'rate'
  discount_value?: number
  discount?: number
  subtotal?: number
}

/** 支付方式固定选项（与后端 PAY_METHOD_OPTIONS 对齐） */
export const PAY_METHOD_OPTIONS = ['微信', '支付宝', 'POS机刷卡', '现金', '其他'] as const
export type PayMethodOption = (typeof PAY_METHOD_OPTIONS)[number]

export interface EnrollmentRecord {
  id: number
  order_id?: number | null
  student_id: number
  student_name?: string | null
  student_grade?: string | null
  student_phone?: string | null
  kind: EnrollmentKind | string
  handled_at?: string | null
  amount: number
  order_no?: string
  pay_methods?: string[]
  pay_other?: string
  courses: EnrollmentCourse[]
  attributions: EnrollmentAttribution[]
  internal_notes: string
  external_notes: string
  internal_images: string[]
  created_by?: number | null
  created_by_name?: string | null
  created_at?: string | null
}

export interface EnrollmentCreateInput {
  student_id: number
  kind: EnrollmentKind
  handled_at?: string | null
  amount?: number
  courses: EnrollmentCourse[]
  attributions?: { user_id: number; amount: number }[]
  pay_methods: string[]
  pay_other?: string
  payments?: { method: string; amount: number }[]
  internal_notes?: string
  external_notes?: string
  internal_images?: string[]
}

export async function listEnrollmentsApi(params: {
  student_id?: number
  kind?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<EnrollmentRecord>> {
  const res = await client.get('/enrollments', {
    params: {
      student_id: params.student_id,
      kind: params.kind || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  return asPageResult<EnrollmentRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function createEnrollmentApi(
  payload: EnrollmentCreateInput,
): Promise<EnrollmentRecord> {
  const res = await client.post('/enrollments', payload)
  return res.data.data
}

export async function uploadEnrollmentNoteImageApi(file: File): Promise<{ path: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post('/enrollments/note-images', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data.data
}

/** 对内备注图预览 URL（需带 token，走 axios blob） */
export async function enrollmentNoteImageObjectUrl(path: string): Promise<string> {
  const res = await client.get('/enrollments/note-images/content', {
    params: { path },
    responseType: 'blob',
  })
  return URL.createObjectURL(res.data)
}
