/*
 * evaluation information start
 * real case = true
 * evaluation item = 跨文件
 * scene introduction = 头文件中的 static inline 函数
 * bind_url = completeness/cross_file/header_inline_002_T
 * evaluation information end
 */
#include "helper.h"
void header_inline_002_T(void) {
    helper_sink(taint_src());
}
