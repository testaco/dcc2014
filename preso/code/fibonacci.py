def fibonacci(N):
    if N > 0:
        yield 1
    m = 1

    f2 = 0
    f1 = 1
    while m < N:
        tmp = f1
        f1 = f2 + f1
        yield f1
        f2 = tmp
        m += 1

assert list(fibonacci(0)) == []
assert list(fibonacci(10)) == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
