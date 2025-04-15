import axios from "axios";

const BASE_URL = "http://localhost:5000"; // Flask backend

export async function fetchStudent(id) {
  return await axios.get(`${BASE_URL}/student/${id}`);
}

export async function fetchProfessor(id) {
  return await axios.get(`${BASE_URL}/professor/${id}`);
}

export async function updateStudent(id, data) {
  return await axios.post(`${BASE_URL}/student/${id}`, data);
}

export async function updateProfessor(id, data) {
  return await axios.post(`${BASE_URL}/professor/${id}`, data);
}

