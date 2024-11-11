import random
import string


def generate_random_four_chars():
    # 定义字符集：数字（0-9）和字母（A-Z）
    characters = string.ascii_uppercase + string.digits

    # 随机选择四个字符
    random_chars = ''.join(random.choice(characters) for _ in range(4))

    return random_chars
