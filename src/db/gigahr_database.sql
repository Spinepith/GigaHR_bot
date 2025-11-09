-- CREATE DATABASE gigahr;


CREATE TABLE IF NOT EXISTS users_data (
    tg_id BIGINT PRIMARY KEY,
    fio TEXT NOT NULL,
    resume TEXT NOT NULL,
    contact TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vacancies (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Свободна', 'Занята'))
);

CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT NOT NULL,
    fio TEXT NOT NULL,
    vacancy_name TEXT NOT NULL REFERENCES vacancies(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS interview_slots (
    id SERIAL PRIMARY KEY,
    vacancy_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    available_date DATE NOT NULL,
    available_time TIME NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    employee_tg_id BIGINT NOT NULL,
    UNIQUE(vacancy_id, available_date, available_time, employee_tg_id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users_data(tg_id) ON DELETE CASCADE,
    slot_id INTEGER NOT NULL REFERENCES interview_slots(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    employee_tg_id BIGINT NOT NULL,
    vacancy_name TEXT NOT NULL,
    user_fio TEXT NOT NULL,
    user_resume TEXT NOT NULL,
    user_contact TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Назначено собеседование', 'На рассмотрении', 'Принят', 'Отказано')),
    last_notified_status TEXT CHECK (status IN ('Назначено собеседование', 'На рассмотрении', 'Принят', 'Отказано')),
    UNIQUE (user_id, slot_id)
);

CREATE TABLE IF NOT EXISTS vacancy_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users_data(tg_id) ON DELETE CASCADE,
    vacancy_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    vacancy_name TEXT NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, vacancy_id)
);

CREATE TABLE IF NOT EXISTS interview_slot_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users_data(tg_id) ON DELETE CASCADE,
    vacancy_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    vacancy_name TEXT NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, vacancy_id)
);

CREATE TABLE IF NOT EXISTS employee_notifications (
    id SERIAL PRIMARY KEY,
    employee_tg_id BIGINT NOT NULL,
    candidate_id INTEGER NOT NULL,
    vacancy_name TEXT NOT NULL,
    user_fio TEXT NOT NULL,
    user_contact TEXT NOT NULL,
    user_resume TEXT NOT NULL,
    available_date DATE NOT NULL,
    available_time TIME NOT NULL,
    is_notified BOOLEAN DEFAULT FALSE,
    action_type TEXT NOT NULL CHECK (action_type IN ('added', 'cancelled')),
    UNIQUE(candidate_id, employee_tg_id, action_type)
);


CREATE INDEX idx_vacancies_name ON vacancies(name);
CREATE INDEX idx_vacancies_status ON vacancies(status);
CREATE INDEX idx_slots_available_datetime ON interview_slots(available_date, available_time) WHERE is_available = TRUE;
CREATE INDEX idx_slots_vacancy ON interview_slots(vacancy_id);
CREATE INDEX idx_candidates_user ON candidates(user_id);
CREATE INDEX idx_candidates_slot ON candidates(slot_id);
CREATE INDEX idx_employees_tg_id ON employees(tg_id);
CREATE INDEX idx_employees_vacancy ON employees(vacancy_name);
CREATE INDEX idx_employees_tg_vacancy ON employees(tg_id, vacancy_name);
CREATE INDEX idx_slots_employee ON interview_slots(employee_tg_id);


CREATE OR REPLACE FUNCTION trg_manage_slot_availability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE interview_slots 
        SET is_available = FALSE 
        WHERE id = NEW.slot_id;
        
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE interview_slots 
        SET is_available = TRUE 
        WHERE id = OLD.slot_id;
        
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.status = 'Назначено собеседование' AND OLD.status != 'Назначено собеседование' THEN
            UPDATE interview_slots 
            SET is_available = FALSE 
            WHERE id = NEW.slot_id;
        ELSIF NEW.status != 'Назначено собеседование' AND OLD.status = 'Назначено собеседование' THEN
            UPDATE interview_slots 
            SET is_available = TRUE 
            WHERE id = NEW.slot_id;
        END IF;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_manage_slot_availability
AFTER INSERT OR UPDATE OR DELETE ON candidates
FOR EACH ROW
EXECUTE FUNCTION trg_manage_slot_availability();


CREATE OR REPLACE FUNCTION trg_mark_subscriptions_notified()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'Занята' AND NEW.status = 'Свободна' THEN
        UPDATE vacancy_subscriptions
        SET is_notified = TRUE
        WHERE vacancy_id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_mark_subscriptions_notified
AFTER UPDATE ON vacancies
FOR EACH ROW
EXECUTE FUNCTION trg_mark_subscriptions_notified();


CREATE OR REPLACE FUNCTION trg_notify_slot_available()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.is_available = TRUE THEN
        UPDATE interview_slot_subscriptions
        SET is_notified = TRUE
        WHERE vacancy_id = NEW.vacancy_id;

    ELSIF TG_OP = 'UPDATE' AND NEW.is_available = TRUE AND OLD.is_available = FALSE THEN
        UPDATE interview_slot_subscriptions
        SET is_notified = TRUE
        WHERE vacancy_id = NEW.vacancy_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_notify_slot_available
AFTER INSERT OR UPDATE ON interview_slots
FOR EACH ROW
EXECUTE FUNCTION trg_notify_slot_available();


CREATE OR REPLACE FUNCTION trg_notify_employee_on_candidate_add()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO employee_notifications (
        employee_tg_id, candidate_id, vacancy_name, user_fio, user_contact, user_resume,
        available_date, available_time, action_type, is_notified
    )
    SELECT
        NEW.employee_tg_id,
        NEW.id,
        NEW.vacancy_name,
        NEW.user_fio,
        NEW.user_contact,
        NEW.user_resume,
        s.available_date,
        s.available_time,
        'added',
        TRUE
    FROM interview_slots s
    WHERE s.id = NEW.slot_id
    ON CONFLICT (candidate_id, employee_tg_id, action_type) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_notify_employee_on_candidate_add
AFTER INSERT ON candidates
FOR EACH ROW
EXECUTE FUNCTION trg_notify_employee_on_candidate_add();


CREATE OR REPLACE FUNCTION trg_notify_employee_on_candidate_delete()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO employee_notifications (
        employee_tg_id, candidate_id, vacancy_name, user_fio, user_contact, user_resume,
        available_date, available_time, action_type, is_notified
    )
    SELECT
        OLD.employee_tg_id,
        OLD.id,
        OLD.vacancy_name,
        OLD.user_fio,
        OLD.user_contact,
        OLD.user_resume,
        s.available_date,
        s.available_time,
        'cancelled',
        TRUE
    FROM interview_slots s
    WHERE s.id = OLD.slot_id
    ON CONFLICT (candidate_id, employee_tg_id, action_type) DO NOTHING;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_notify_employee_on_candidate_delete
AFTER DELETE ON candidates
FOR EACH ROW
EXECUTE FUNCTION trg_notify_employee_on_candidate_delete();


CREATE OR REPLACE VIEW available_slots_view AS
SELECT 
    s.id AS slot_id,
    s.available_date,
    s.available_time,
    v.id AS vacancy_id,
    v.name AS vacancy_name,
    s.employee_tg_id,
    e.fio AS employee_fio
FROM interview_slots s
JOIN vacancies v ON s.vacancy_id = v.id
LEFT JOIN employees e ON e.tg_id = s.employee_tg_id AND e.vacancy_name = v.name
WHERE s.is_available = TRUE AND v.status = 'Свободна';


CREATE OR REPLACE VIEW candidates_detailed_view AS
SELECT 
    c.id AS candidate_id,
    c.user_id,
    c.user_fio,
    c.user_resume,
    c.user_contact,
    c.status,
    v.name AS vacancy_name,
    s.available_date,
    s.available_time,
    c.employee_tg_id,
    e.fio AS employee_fio
FROM candidates c
LEFT JOIN interview_slots s ON c.slot_id = s.id
LEFT JOIN vacancies v ON s.vacancy_id = v.id
LEFT JOIN employees e ON e.tg_id = c.employee_tg_id AND e.vacancy_name = v.name;


CREATE OR REPLACE VIEW employee_interviews_view AS
SELECT 
    c.employee_tg_id,
    e.fio AS employee_fio,
    v.name AS vacancy_name,
    c.user_fio AS candidate_fio,
    c.user_contact AS candidate_contact,
    c.user_resume AS candidate_resume,
    s.available_date,
    s.available_time,
    c.status AS interview_status,
    c.id AS candidate_id
FROM candidates c
JOIN interview_slots s ON c.slot_id = s.id
JOIN vacancies v ON s.vacancy_id = v.id
LEFT JOIN employees e ON e.tg_id = c.employee_tg_id AND e.vacancy_name = v.name
ORDER BY s.available_date, s.available_time;