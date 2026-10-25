/*
 * evaluation information start
 * real case = true
 * evaluation item = 数组
 * scene introduction = 二维数组
 * bind_url = accuracy/field_sensitive/array/array_2d_005_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void array_2d_005_T(void) {
    char *grid[2][2];
    grid[1][0] = taint_src();
    taint_sink(grid[1][0]);
}
