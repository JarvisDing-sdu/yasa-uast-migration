/*
 * evaluation information start
 * real case = false
 * evaluation item = 数组
 * scene introduction = 初始化列表中区分下标
 * bind_url = accuracy/field_sensitive/array/array_init_004_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void array_init_004_F(void) {
    char *arr[] = { taint_src(), "safe" };
    taint_sink(arr[1]);
}
