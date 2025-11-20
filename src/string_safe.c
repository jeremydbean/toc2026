#include "merc.h"

size_t toc_strnlen(const char *src, size_t maxlen)
{
    size_t len;

    if (src == NULL)
    {
        return 0;
    }

    for (len = 0; len < maxlen && src[len] != '\0'; ++len)
    {
        /* Intentionally empty: all work happens in the loop header. */
    }

    return len;
}

#ifndef __APPLE__
size_t strlcpy(char *dst, const char *src, size_t siz)
{
    size_t src_len = strlen(src);

    if (siz > 0)
    {
        size_t copy_len = (src_len >= siz) ? siz - 1 : src_len;
        memcpy(dst, src, copy_len);
        dst[copy_len] = '\0';
    }

    return src_len;
}

size_t strlcat(char *dst, const char *src, size_t siz)
{
    size_t dst_len = strlen(dst);
    size_t src_len = strlen(src);

    if (dst_len < siz)
    {
        size_t copy_len = siz - dst_len - 1;

        if (copy_len > 0)
        {
            if (copy_len > src_len)
            {
                copy_len = src_len;
            }

            memcpy(dst + dst_len, src, copy_len);
            dst[dst_len + copy_len] = '\0';
        }
    }

    return dst_len + src_len;
}
#endif
