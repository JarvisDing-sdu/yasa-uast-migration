/*
 * evaluation information start
 * real case = true
 * evaluation item = 数组
 * scene introduction = 初始化列表中的污点
 * bind_url = accuracy/field_sensitive/array/array_init_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void array_init_003_T(void) {
    char *arr[] = { taint_src(), "safe" };
    taint_sink(arr[0]);
}
