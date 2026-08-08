import { computed, type Component } from 'vue'
import { ElDialog } from 'element-plus'
import AppSheet from '../components/AppSheet.vue'
import { useBreakpoint } from './useBreakpoint'

export type ResponsiveSurfaceOptions = {
  /** AppSheet 窄屏高度，默认手机 92% / Pad 竖屏 78% */
  compactSize?: string | number
  /** AppSheet / 侧栏桌面宽度 */
  size?: string | number
  /** 传给 AppSheet 的 modalClass */
  modalClass?: string
  /** PC Dialog 宽度 */
  dialogWidth?: string
  /** PC Dialog maxWidth（写在 style 上） */
  dialogMaxWidth?: string
  /** 额外 PC Dialog 属性 */
  dialogProps?: Record<string, unknown>
  /** 额外 AppSheet 属性 */
  sheetProps?: Record<string, unknown>
}

/**
 * PC 用 ElDialog、WAP/Pad 用 AppSheet 的统一表面。
 *
 * @example
 * const { surface, surfaceProps } = useResponsiveSurface({ dialogMaxWidth: '560px' })
 * <component :is="surface" v-model="visible" v-bind="surfaceProps" title="编辑">
 */
export function useResponsiveSurface(options?: ResponsiveSurfaceOptions) {
  const { isApp, isMobile } = useBreakpoint()

  const surface = computed<Component>(() => (isApp.value ? AppSheet : ElDialog))

  const surfaceProps = computed(() => {
    if (isApp.value) {
      const compact =
        options?.compactSize ?? (isMobile.value ? '92%' : '78%')
      return {
        size: options?.size ?? '460px',
        compactSize: compact,
        destroyOnClose: true,
        appendToBody: true,
        modalClass: options?.modalClass ?? '',
        ...(options?.sheetProps ?? {}),
      }
    }
    return {
      width: options?.dialogWidth ?? '90%',
      style: { maxWidth: options?.dialogMaxWidth ?? '560px' },
      destroyOnClose: true,
      appendToBody: true,
      alignCenter: true,
      ...(options?.dialogProps ?? {}),
    }
  })

  return {
    isApp,
    isMobile,
    surface,
    surfaceProps,
  }
}
