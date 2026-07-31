/** 文案模板 {{变量}} 说明：含义 + 数据来源 */
export interface TemplateParamHint {
  key: string
  label: string
  /** 灰色提示：从哪里取值 */
  source: string
  /** 在生成页对应的表单项（可选） */
  usedIn?: string
}

/** 文案模板可用占位符（与 backend content.service._build_context 对齐） */
export const COPY_TEMPLATE_PARAMS: TemplateParamHint[] = [
  {
    key: 'title',
    label: '场景标题',
    source: '来自「素材」标题；生成文案时选择素材后自动填入',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'grade',
    label: '年级',
    source: '来自「素材」年级字段',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'subject',
    label: '科目',
    source: '来自「素材」科目字段',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'pain_point',
    label: '家长痛点',
    source: '来自「素材」家长痛点；上传/编辑素材时填写',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'teacher_action',
    label: '老师处理',
    source: '来自「素材」老师处理；上传/编辑素材时填写',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'next_step',
    label: '下一步行动',
    source: '来自「素材」下一步行动；上传/编辑素材时填写',
    usedIn: '生成文案 · 素材',
  },
  {
    key: 'tone',
    label: '话术/语气参考',
    source: '来自「成长中心 · 沟通话术」启用条目（自动汇总）',
    usedIn: '成长中心 · 沟通话术',
  },
]

/** 海报 layout_json 顶层配置 */
export const POSTER_LAYOUT_META: TemplateParamHint[] = [
  {
    key: 'width',
    label: '画布宽度',
    source: '版式导出时图片像素宽，常用 750',
  },
  {
    key: 'height',
    label: '画布高度',
    source: '版式导出时图片像素高，常用 1000',
  },
  {
    key: 'background',
    label: '背景色',
    source: '十六进制颜色，如 #176b4d',
  },
  {
    key: 'fields',
    label: '文字字段列表',
    source: '每个 field 的 key 对应生成海报页填写的文案',
  },
]

/** fields[] 单项属性 */
export const POSTER_FIELD_META: TemplateParamHint[] = [
  {
    key: 'key',
    label: '字段名',
    source: '与生成页参数对应：title / subtitle / footer（可自定义 key，需在生成时传入同名值）',
    usedIn: '生成海报 · 标题/副标题/页脚',
  },
  {
    key: 'x',
    label: '横坐标',
    source: '文字左上角距画布左侧的像素',
  },
  {
    key: 'y',
    label: '纵坐标',
    source: '文字左上角距画布顶部的像素',
  },
  {
    key: 'font_size',
    label: '字号',
    source: '像素字号，如 48',
  },
  {
    key: 'fill',
    label: '文字颜色',
    source: '十六进制颜色，如 #ffffff',
  },
]

/** 生成海报页表单字段与模板 key 的对应 */
export const POSTER_GENERATE_FIELDS: TemplateParamHint[] = [
  {
    key: 'title',
    label: '标题',
    source: '对应模板 fields 中 key 为 title 的文字；本页直接填写',
    usedIn: '海报模板 · fields.key=title',
  },
  {
    key: 'subtitle',
    label: '副标题',
    source: '对应模板 fields 中 key 为 subtitle 的文字；本页直接填写',
    usedIn: '海报模板 · fields.key=subtitle',
  },
  {
    key: 'footer',
    label: '页脚',
    source: '对应模板 fields 中 key 为 footer 的文字；本页直接填写',
    usedIn: '海报模板 · fields.key=footer',
  },
]

export function copyParamPlaceholder(key: string) {
  return `{{${key}}}`
}
