// Minimal JSON reader for the fixed m3d-instance format (docs/FORMATS.md).
// Parses objects, arrays, numbers, strings, true/false/null. No writer: output is
// emitted directly by the router.
#pragma once
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mj {

struct Value {
  enum Kind { Null, Bool, Num, Str, Arr, Obj } kind = Null;
  double num = 0;
  bool b = false;
  std::string str;
  std::vector<Value> arr;
  // object members as parallel vectors (a vector of pair<string, Value> needs Value complete,
  // which clang/libc++ enforce)
  std::vector<std::string> keys;
  std::vector<Value> vals;

  const Value* find(const std::string& k) const {
    for (size_t i = 0; i < keys.size(); ++i)
      if (keys[i] == k) return &vals[i];
    return nullptr;
  }
  const Value& at(const std::string& k) const {
    const Value* v = find(k);
    if (!v) throw std::runtime_error("json: missing key " + k);
    return *v;
  }
  const Value& at(size_t i) const { return arr.at(i); }
  size_t size() const { return kind == Arr ? arr.size() : keys.size(); }
  long long as_int() const { return static_cast<long long>(num); }
};

class Parser {
 public:
  Parser(const char* p, const char* e) : p_(p), e_(e) {}
  Value parse() {
    Value v = value();
    ws();
    if (p_ != e_) fail("trailing characters");
    return v;
  }

 private:
  const char* p_;
  const char* e_;

  [[noreturn]] void fail(const char* msg) { throw std::runtime_error(std::string("json: ") + msg); }
  void ws() {
    while (p_ < e_ && (*p_ == ' ' || *p_ == '\n' || *p_ == '\r' || *p_ == '\t')) ++p_;
  }
  void expect(char c) {
    ws();
    if (p_ >= e_ || *p_ != c) fail("unexpected character");
    ++p_;
  }
  Value value() {
    ws();
    if (p_ >= e_) fail("unexpected end");
    Value v;
    char c = *p_;
    if (c == '{') {
      v.kind = Value::Obj;
      ++p_;
      ws();
      if (p_ < e_ && *p_ == '}') { ++p_; return v; }
      while (true) {
        ws();
        std::string k = string_lit();
        expect(':');
        v.keys.push_back(std::move(k));
        v.vals.push_back(value());
        ws();
        if (p_ < e_ && *p_ == ',') { ++p_; continue; }
        expect('}');
        return v;
      }
    }
    if (c == '[') {
      v.kind = Value::Arr;
      ++p_;
      ws();
      if (p_ < e_ && *p_ == ']') { ++p_; return v; }
      while (true) {
        v.arr.push_back(value());
        ws();
        if (p_ < e_ && *p_ == ',') { ++p_; continue; }
        expect(']');
        return v;
      }
    }
    if (c == '"') {
      v.kind = Value::Str;
      v.str = string_lit();
      return v;
    }
    if (c == 't' || c == 'f' || c == 'n') {
      const char* word = c == 't' ? "true" : c == 'f' ? "false" : "null";
      size_t n = c == 'f' ? 5 : 4;
      if (static_cast<size_t>(e_ - p_) < n || std::string(p_, n) != word) fail("bad literal");
      p_ += n;
      v.kind = c == 'n' ? Value::Null : Value::Bool;
      v.b = c == 't';
      return v;
    }
    char* end = nullptr;
    v.num = std::strtod(p_, &end);
    if (end == p_) fail("bad number");
    v.kind = Value::Num;
    p_ = end;
    return v;
  }
  std::string string_lit() {
    ws();
    if (p_ >= e_ || *p_ != '"') fail("expected string");
    ++p_;
    std::string s;
    while (p_ < e_ && *p_ != '"') {
      if (*p_ == '\\') {
        ++p_;
        if (p_ >= e_) fail("bad escape");
        char c = *p_;
        if (c == 'u') {
          if (e_ - p_ < 5) fail("bad unicode escape");
          unsigned code = static_cast<unsigned>(std::strtoul(std::string(p_ + 1, 4).c_str(), nullptr, 16));
          if (code < 0x80) s += static_cast<char>(code);
          else s += '?';
          p_ += 5;
          continue;
        }
        s += c == 'n' ? '\n' : c == 't' ? '\t' : c == 'r' ? '\r' : c == 'b' ? '\b' : c == 'f' ? '\f' : c;
        ++p_;
      } else {
        s += *p_++;
      }
    }
    if (p_ >= e_) fail("unterminated string");
    ++p_;
    return s;
  }
};

inline Value parse(const std::string& text) {
  const char* b = text.data();
  const char* e = b + text.size();
  if (e - b >= 3 && static_cast<unsigned char>(b[0]) == 0xEF && static_cast<unsigned char>(b[1]) == 0xBB &&
      static_cast<unsigned char>(b[2]) == 0xBF)
    b += 3;  // UTF-8 BOM
  return Parser(b, e).parse();
}

}  // namespace mj
