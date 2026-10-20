def request_access(self, email: str, platform: str) -> AccessToken:
        normalized_email = validate_email(email)
        normalized_platform = normalize_platform(platform)
        logger.info("Access request received for %s on %s", mask_email(normalized_email), normalized_platform)
        profile = self._fetch_profile(normalized_email, normalized_platform)
        verify_profile(profile, self.policy, now=self.clock())
        now = self.clock()
        with self.store.transaction() as tokens:
            self._prune_expired(tokens, now)
            existing = self._find_active(tokens, normalized_email, normalized_platform, now)
            if existing is not None:
                logger.info("Reusing active token ...")
                return existing
            token = issue_token(profile, self.settings, now=now)
            tokens[token.digest] = token
            return token