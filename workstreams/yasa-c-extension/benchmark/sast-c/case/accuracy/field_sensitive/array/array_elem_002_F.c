/*
 * evaluation information start
 * real case = false
 * evaluation item = 数组
 * scene introduction = 区分数组不同下标
 * bind_url = accuracy/field_sensitive/array/array_elem_002_F
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void array_elem_002_F(void) {
    char *arr[2];
    arr[0] = taint_src();
    arr[1] = "safe";
    taint_sink(arr[1]);
}
