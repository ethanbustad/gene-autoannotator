import logging
import time

import cloudscraper as cs

import utils

COOLDOWN_SECONDS_DEFAULT = 0.5
TIMEOUT_SECONDS_DEFAULT = 60

logging.basicConfig(format='%(asctime)s %(levelname).1s | %(message)s')
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Throttler:
    def __init__(self, cooldown_secs=None, timeout_secs=None):
        self.cooldown_seconds = COOLDOWN_SECONDS_DEFAULT if cooldown_secs is None else cooldown_secs
        self.last_requests = {}
        self.scraper = cs.create_scraper()
        self.timeout = TIMEOUT_SECONDS_DEFAULT if timeout_secs is None else timeout_secs
        if self.cooldown_seconds <= 1:
            log.info(
                f'Using throttler to make no more than {1/self.cooldown_seconds:.0f} ' + \
                    f'request{utils.s_if_plural(self.cooldown_seconds)} per second'
            )
        else:
            log.info(
                f'Using throttler to make no more than one request per ' + \
                    f'{self.cooldown_seconds} seconds'
            )

    def get(self, url, base_url):
        return self.throttle(
            base_url,
            lambda: self.scraper.get(url, timeout=self.timeout)
        )

    def throttle(self, label, throttled_function):
        if label in self.last_requests:
            time_passed = time.time() - self.last_requests[label]
            if time_passed < self.cooldown_seconds:
                wait_time = self.cooldown_seconds - time_passed
                log.debug(f'Slowing down requests: sleeping for {wait_time:.3f}s')
                time.sleep(wait_time)
        return_value = throttled_function()
        self.last_requests[label] = time.time()
        return return_value
