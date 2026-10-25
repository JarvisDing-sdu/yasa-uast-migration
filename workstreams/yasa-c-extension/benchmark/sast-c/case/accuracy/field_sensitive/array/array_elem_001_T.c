/*
 * evaluation information start
 * real case = true
 * evaluation item = 数组
 * scene introduction = 数组元素赋值
 * bind_url = accuracy/field_sensitive/array/array_elem_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void array_elem_001_T(void) {
    char *arr[2];
    arr[0] = taint_src();
    taint_sink(arr[0]);
}
