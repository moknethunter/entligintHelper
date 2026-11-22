-- بيانات اصطناعية للتجربة المحلية.
CREATE TABLE daleel_accounts (code TEXT PRIMARY KEY, name TEXT, kind TEXT, currency TEXT);
CREATE TABLE daleel_cashboxes (code TEXT PRIMARY KEY, name TEXT, account_code TEXT, currency TEXT);
CREATE TABLE daleel_trial_balance (
    start_date TEXT NOT NULL, end_date TEXT NOT NULL, account_code TEXT NOT NULL,
    currency TEXT NOT NULL, debit TEXT NOT NULL, credit TEXT NOT NULL,
    PRIMARY KEY (start_date, end_date, account_code, currency)
);
INSERT INTO daleel_accounts VALUES
    ('1010', 'الصندوق الرئيسي', 'أصول', 'YER'),
    ('3100', 'رأس المال', 'حقوق ملكية', 'YER');
INSERT INTO daleel_cashboxes VALUES ('MAIN', 'الصندوق الرئيسي', '1010', 'YER');
INSERT INTO daleel_trial_balance VALUES
    ('2026-11-01', '2026-11-30', '1010', 'YER', '125000.25', '0.00'),
    ('2026-11-01', '2026-11-30', '3100', 'YER', '0.00', '125000.25');
