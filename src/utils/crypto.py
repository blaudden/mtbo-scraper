import base64


class Crypto:
    """Simple encryption helper using XOR cipher + Base64 encoding.

    Used for obfuscating sensitive data like emails in storage.
    """

    KEY = "mtbo-scraper"

    @staticmethod
    def encrypt(text: str) -> str:
        """Encrypts text using XOR with KEY and returns base64 string.

        Prefixes result with 'enc:' to identify encrypted values.

        Args:
           text: The plain text to encrypt.

        Returns:
           The encrypted string starting with 'enc:'. Returns empty
           string if text is empty.
        """
        if not text:
            return ""

        # XOR
        xor_bytes = bytearray()
        key_len = len(Crypto.KEY)
        text_bytes = text.encode("utf-8")

        for i, b in enumerate(text_bytes):
            xor_bytes.append(b ^ ord(Crypto.KEY[i % key_len]))

        # Base64 encode
        b64 = base64.b64encode(xor_bytes).decode("utf-8")
        return f"enc:{b64}"

    @staticmethod
    def decrypt(enc_text: str) -> str:
        """Decrypts 'enc:{base64}' string back to original text.

        Args:
            enc_text: The encrypted string to decrypt.

        Returns:
            The decrypted original text. Returns original input if not
            in valid 'enc:' format.
        """
        if not enc_text or not enc_text.startswith("enc:"):
            return enc_text

        try:
            b64 = enc_text[4:]
            xor_bytes = base64.b64decode(b64)

            # XOR reverse
            res_bytes = bytearray()
            key_len = len(Crypto.KEY)

            for i, b in enumerate(xor_bytes):
                res_bytes.append(b ^ ord(Crypto.KEY[i % key_len]))

            return res_bytes.decode("utf-8")
        except Exception:
            return enc_text
