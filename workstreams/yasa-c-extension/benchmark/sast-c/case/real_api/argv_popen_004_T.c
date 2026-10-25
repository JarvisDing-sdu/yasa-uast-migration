/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = main 的 argv → popen
 * bind_url = real_api/argv_popen_004_T
 * evaluation information end
 */
#include <stdio.h>
int main(int argc, char **argv) {
    FILE *f = popen(argv[1], "r");
    return f != 0;
}
