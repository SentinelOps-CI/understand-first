//! Small Rust fixture for Understand-First Wave 22.

pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

pub fn compute(x: i32, y: i32) -> i32 {
    add(x, y)
}

pub fn classify(n: i32) -> &'static str {
    if n < 0 {
        return "neg";
    }
    for i in 0..n {
        if i > 10 && i < 20 {
            return "mid";
        }
    }
    match n {
        0 => "zero",
        _ => "other",
    }
}

pub struct Calc {
    pub n: i32,
}

impl Calc {
    pub fn scale(&self, v: i32) -> i32 {
        add(v, 0)
    }

    pub fn run(&self, a: i32, b: i32) -> i32 {
        self.scale(compute(a, b))
    }
}
