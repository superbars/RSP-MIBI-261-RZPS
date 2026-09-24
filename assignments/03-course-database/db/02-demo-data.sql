INSERT INTO teachers (name, email) VALUES
('Test teacher', 'test@example.com'),
('Test teacher2', 'test2@example.com');


INSERT INTO courses (title, teacher_id) VALUES
    ('Database', 1),
    ('Software development', 1),
    ('Networks', 2);

INSERT INTO students (name, email) VALUES
    ('Test Student1', 'student1@example.com'),
    ('Test Student2', 'student2@example.com'),
    ('Test Student3', 'student3@example.com');

INSERT INTO enrollments (student_id, course_id, grade) VALUES
    (1, 1, 8),
    (1, 2, 9),
    (2, 1, 7),
    (3, 3, 2);
