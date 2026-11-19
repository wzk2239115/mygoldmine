#include <stdio.h>
#include <string.h>
#include "targets_tlse.c"

int main(void) {
    unsigned char der[] = {0x30, 0x06, 0x30, 0x00, 0x30, 0x00, 0x03, 0x00};
    struct TLSCertificate *cert;
    cert = tls_certificate_parse(der, sizeof(der));
    if (cert) tls_destroy_certificate(cert);
    return 0;
}
