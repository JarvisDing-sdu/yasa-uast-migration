/*
 * evaluation information start
 * real case = true
 * evaluation item = 跨文件
 * scene introduction = 另一个文件中函数的返回值
 * bind_url = completeness/cross_file/cross_file_return_003_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
char *fetch_other(void);
void cross_file_return_003_T(void) {
    taint_sink(fetch_other());
}
