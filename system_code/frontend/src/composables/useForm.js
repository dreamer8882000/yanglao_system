/**
 * 表单组合式函数
 */

import { ref, reactive } from 'vue';
import { validateForm } from '../utils/validation';

export function useForm(options = {}) {
  const {
    initialValues = {},
    rules = {},
    onSubmit = null
  } = options;

  const formData = reactive({ ...initialValues });
  const errors = reactive({});
  const loading = ref(false);
  const touched = reactive({});

  const setFieldValue = (field, value) => {
    formData[field] = value;
    touched[field] = true;
    validateField(field);
  };

  const setFieldError = (field, error) => {
    errors[field] = error;
  };

  const validateField = (field) => {
    if (!rules[field]) return true;
    
    const fieldRules = Array.isArray(rules[field]) ? rules[field] : [rules[field]];
    const value = formData[field];
    
    for (const rule of fieldRules) {
      const error = rule(value, formData);
      if (error) {
        errors[field] = error;
        return false;
      }
    }
    
    errors[field] = '';
    return true;
  };

  const validate = () => {
    let isValid = true;
    
    for (const field in rules) {
      if (!validateField(field)) {
        isValid = false;
      }
    }
    
    return isValid;
  };

  const handleSubmit = async () => {
    // 标记所有字段为已触摸
    Object.keys(formData).forEach(key => {
      touched[key] = true;
    });

    if (!validate()) {
      return false;
    }

    if (onSubmit) {
      loading.value = true;
      try {
        await onSubmit(formData);
        return true;
      } catch (error) {
        console.error('Form submission error:', error);
        return false;
      } finally {
        loading.value = false;
      }
    }
    
    return true;
  };

  const reset = () => {
    Object.assign(formData, initialValues);
    Object.keys(errors).forEach(key => {
      errors[key] = '';
    });
    Object.keys(touched).forEach(key => {
      touched[key] = false;
    });
  };

  return {
    formData,
    errors,
    loading,
    touched,
    setFieldValue,
    setFieldError,
    validateField,
    validate,
    handleSubmit,
    reset
  };
}
