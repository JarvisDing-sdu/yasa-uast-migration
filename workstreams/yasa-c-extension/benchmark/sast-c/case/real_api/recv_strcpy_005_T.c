/*
 * evaluation information start
 * real case = true
 * evaluation item = 真实 API
 * scene introduction = recv → strcpy 缓冲区溢出
 * bind_url = real_api/recv_strcpy_005_T
 * evaluation information end
 */
#include <string.h>
#include <sys/socket.h>
void recv_strcpy_005_T(int sock) {
    char in[256];
    char small[8];
    recv(sock, in, sizeof(in), 0);
    strcpy(small, in);
}
