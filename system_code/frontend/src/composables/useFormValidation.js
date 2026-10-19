import { ref, reactive } from 'vue';

export function useFormValidation() {
  const errors = reactive({});
  const touched = reactive({});

  const rules = {
    required: (value, message = '此字段为必填项') => {
      if (value === null || value === undefined || value === '') {
        return message;
      }
      if (typeof value === 'string' && value.trim() === '') {
        return message;
      }
      return null;
    },

    minLength: (min, message) => (value) => {
      if (!value || value.length < min) {
        return message || `至少需要 ${min} 个字符`;
      }
      return null;
    },

    maxLength: (max, message) => (value) => {
      if (value && value.length > max) {
        return message || `最多 ${max} 个字符`;
      }
      return null;
    },

    email: (value, message = '请输入有效的邮箱地址') => {
      if (!value) return null;
      const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return pattern.test(value) ? null : message;
    },

    phone: (value, message = '请输入有效的手机号码') => {
      if (!value) return null;
      const pattern = /^1[3-9]\d{9}$/;
      return pattern.test(value) ? null : message;
    },

    number: (value, message = '请输入有效的数字') => {
      if (!value) return null;
      return !isNaN(value) ? null : message;
    },

    min: (min, message) => (value) => {
      if (!value) return null;
      const num = parseFloat(value);
      return num >= min ? null : (message || `值不能小于 ${min}`);
    },

    max: (max, message) => (value) => {
      if (!value) return null;
      const num = parseFloat(value);
      return num <= max ? null : (message || `值不能大于 ${max}`);
    },

    pattern: (regex, message = '格式不正确') => (value) => {
      if (!value) return null;
      return regex.test(value) ? null : message;
    },
  };

  function validate(field, value, fieldRules) {
    touched[field] = true;
    
    if (!fieldRules || fieldRules.length === 0) {
      errors[field] = null;
      return true;
    }

    for (const rule of fieldRules) {
      let error = null;
      if (typeof rule === 'function') {
        error = rule(value);
      } else if (typeof rule === 'object' && rule.validator) {
        error = rule.validator(value);
      }

      if (error) {
        errors[field] = error;
        return false;
      }
    }

    errors[field] = null;
    return true;
  }

  function validateAll(formData, validationRules) {
    let isValid = true;
    Object.keys(validationRules).forEach(field => {
      const fieldValid = validate(field, formData[field], validationRules[field]);
      if (!fieldValid) isValid = false;
    });
    return isValid;
  }

  function reset() {
    Object.keys(errors).forEach(key => { errors[key] = null; });
    Object.keys(touched).forEach(key => { touched[key] = false; });
  }

  function setError(field, message) {
    errors[field] = message;
    touched[field] = true;
  }

  return {
    errors,
    touched,
    rules,
    validate,
    validateAll,
    reset,
    setError,
  };
}
