/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = getenv → fopen 路径穿越
 * bind_url = real_api/getenv_fopen_006_T
 * evaluation information end
 */
#include <stdio.h>
#include <stdlib.h>
void getenv_fopen_006_T(void) {
    FILE *f = fopen(getenv("CONFIG_PATH"), "r");
    if (f) fclose(f);
}
