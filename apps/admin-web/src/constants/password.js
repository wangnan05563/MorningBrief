/**
 * 改密最小长度：与后端 backend/app/core/security.py 的 MIN_ADMIN_PASSWORD_LEN
 * 是同一口径（《详细设计说明书》change-password minLength 8）。
 * help-fact-claims 门禁会比对「后端常量 / 本文件 / 帮助页正文」三者，改一处必须三处一起改。
 */
export const MIN_ADMIN_PASSWORD_LEN = 8
