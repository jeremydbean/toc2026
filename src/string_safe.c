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

size_t toc_strlcpy(char *dst, const char *src, size_t siz)
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

size_t toc_strlcat(char *dst, const char *src, size_t siz)
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

/*
 * A number to one decimal place -- "12.3", "-0.5" -- held to [-limit,
 * limit] (NaN reads 0) and written through integers, so the text has a
 * length the buffer is known to hold. "%.1f" of an arbitrary double is up
 * to 312 bytes, and an snprintf of it into a short buffer was cut short
 * (format-truncation review, 2026-11-12). Rounds half away from zero, where
 * "%.1f" rounds the binary value half to even: a last digit can differ
 * from printf's at an exact half. Returns buf.
 */
const char *format_tenths(char *buf, size_t size, double value, double limit)
{
    char text[48];
    long long tenths;
    double v = value;

    if (buf == NULL || size == 0)
    {
        return "";
    }
    if (!(limit >= 0.0) || limit > 1e15)
    {
        limit = 1e15;
    }
    if (v != v)
    {
        v = 0.0;
    }
    if (v > limit)
    {
        v = limit;
    }
    if (v < -limit)
    {
        v = -limit;
    }
    tenths = (long long) (v * 10.0 + (v < 0.0 ? -0.5 : 0.5));
    if (tenths < 0)
    {
        tenths = -tenths;
    }
    /* At most 1e16 tenths: "-1000000000000000.0", 19 bytes and the nul. */
    snprintf(text, sizeof(text), "%s%lld.%d", v < 0.0 && tenths > 0 ? "-" : "",
             tenths / 10, (int) (tenths % 10));
    toc_strlcpy(buf, text, size);
    return buf;
}

/*
 * dir, sep and name joined into dst: true only when all of it fits, and
 * dst is "" otherwise, so a path is never used cut short (format-truncation
 * review, 2026-11-12). Copied, not printed: a directory entry's d_name is
 * the trailing array of struct dirent, which gcc 15 does not bound, and an
 * snprintf of it was reported however short the names really are.
 */
bool toc_path_join(char *dst, size_t size, const char *dir, const char *sep,
                   const char *name)
{
    size_t a, b, c;

    if (dst == NULL || size == 0)
    {
        return false;
    }
    dst[0] = '\0';
    a = dir != NULL ? strlen(dir) : 0;
    b = sep != NULL ? strlen(sep) : 0;
    c = name != NULL ? strlen(name) : 0;
    if (a >= size || b >= size - a || c >= size - a - b)
    {
        return false;
    }
    if (a > 0)
    {
        memcpy(dst, dir, a);
    }
    if (b > 0)
    {
        memcpy(dst + a, sep, b);
    }
    if (c > 0)
    {
        memcpy(dst + a + b, name, c);
    }
    dst[a + b + c] = '\0';
    return true;
}
