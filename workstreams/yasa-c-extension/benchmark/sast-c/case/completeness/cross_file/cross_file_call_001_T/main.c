/*
 * evaluation information start
 * real case = true
 * evaluation item = 跨文件
 * scene introduction = 调用另一个文件中的函数
 * bind_url = completeness/cross_file/cross_file_call_001_T
 * evaluation information end
 */
char *taint_src(void);
void taint_sink(const char *s);
void consume_other(char *x);
void cross_file_call_001_T(void) {
    consume_other(taint_src());
}
