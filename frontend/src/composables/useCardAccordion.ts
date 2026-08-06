import { ref } from 'vue'

export type AccordionId = string | number

/**
 * wap/pad 列表卡片互斥展开：同时最多一张展开。
 * 再点同一张则收起。
 */
export function useCardAccordion() {
  const expandedId = ref<AccordionId | null>(null)

  function isExpanded(id: AccordionId) {
    return expandedId.value === id
  }

  function toggle(id: AccordionId, event?: Event) {
    // 点选框 / 链接 / 按钮时不切换折叠
    const t = event?.target
    if (t instanceof Element) {
      if (
        t.closest(
          'button, a, input, textarea, select, label, .el-checkbox, .el-switch, .el-select, .el-date-editor, .el-input, .el-button',
        )
      ) {
        return
      }
    }
    expandedId.value = expandedId.value === id ? null : id
  }

  /** 仅切换折叠，不做控件排除（用于明确的折叠按钮） */
  function toggleForce(id: AccordionId) {
    expandedId.value = expandedId.value === id ? null : id
  }

  function expand(id: AccordionId) {
    expandedId.value = id
  }

  function collapseAll() {
    expandedId.value = null
  }

  return {
    expandedId,
    isExpanded,
    toggle,
    toggleForce,
    expand,
    collapseAll,
  }
}
