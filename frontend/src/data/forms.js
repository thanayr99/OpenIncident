export const initialAccountForm = {
  name: "",
  email: "",
  team: "",
  password: "",
};

export const initialProjectForm = {
  project_id: "",
  name: "",
  base_url: "",
  frontend_url: "",
  backend_url: "",
  repository_url: "",
  healthcheck_path: "/health",
  frontend_healthcheck_path: "/",
  backend_healthcheck_path: "/health",
};

export const initialStoryForm = {
  title: "User can login",
  description: "Login page should render sign in form",
  acceptance_criteria: "Login page loads\nSign in form is visible",
  tags: "frontend,login",
};
