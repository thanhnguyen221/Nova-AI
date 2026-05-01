\documentclass[letterpaper,11pt]{article}
\usepackage{graphicx}
\graphicspath{ {images/} }
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}
\usepackage{bibentry}
\usepackage[export]{adjustbox}
\usepackage{wrapfig}


\usepackage{resume}

\begin{document}
%----------HEADING----------
\begin{center}
    \textbf{\Huge \scshape Thanh Nguyen-Nhut} \\ \vspace{1pt}
    {\color{Blue} (+84) 797620052} $|$
    \href{mailto:thanhfff55@gmail.com}{\color{Blue}thanhfff55@gmail.com} $|$ 
    \href{www.linkedin.com/in/nhut-thanh-nguyen-6041343b2}{\color{Blue}LinkedIn} $|$
    \href{https://github.com/thanhnguyen221}{\color{Blue}GitHub}    
\end{center}


% %-----------EDUCATION-----------
% \section{Objective}
% AI/ML enthusiast with a focus on Generative AI, Large Language Models (LLMs), and Computer Vision. Experienced in problem-solving, research, and collaborative work, with strong communication skills and a continuous learning mindset. Motivated by curiosity and committed to developing innovative AI solutions that solve real-world problems and deliver impact.


\section{EDUCATION}
  \resumeSubHeadingListStart
    \resumeSubheading
      {Kien Giang University}{2022 -- 2026}
      {Bachelor of Information Technology}{GPA: 3.01/4}
      \resumeItemListStart
        \resumeItem{Awarded \textbf{Academic Encouragement Scholarship} for 3 semesters}
        \resumeItem{Participated in \textbf{Faculty-level Scientific Research}: Developed a Social Networking Web Application}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

% \resumeSubHeadingListStart
%     \resumeSubheading
%       {AI VIETNAM}{Ho Chi Minh, Vietnam}
%       {AIO 2022}{Jun. 2022 -- Jun. 2023}
%       \resumeItemListStart
%       \resumeItem{A comprehensive course offering a solid foundation in Artificial Intelligence, covering a wide range of advanced topics such as Machine Learning, Deep Learning, Generative AI, Computer Vision, Natural Language Processing. The course is designed to equip learners with both theoretical knowledge and practical skills across these cutting-edge fields.}
%       \resumeItemListEnd
%   \resumeSubHeadingListEnd


\section{WORK EXPERIENCE}
  \resumeSubHeadingListStart
    
    \resumeSubheading
      {VNPT Kien Giang}{Feb. 2025 -- Jun. 2025}
      {Web Developer Intern}{Kien Giang, Vietnam}
      \resumeItemListStart
        \resumeItem{Analyzed software requirement specifications provided by the technical mentor to design and architect a full-stack \textbf{Task Management Web Application} from scratch using \textbf{Python}, \textbf{Django}, and \textbf{SQLite}.}
        \resumeItem{Built a role-based access control system (Manager/Employee), enabling managers to assign tasks, attach documents, and monitor workflows efficiently.}
        \resumeItem{Developed automated email notifications for new tasks, data export capabilities (\textbf{Excel, PDF, Word}), and an analytical dashboard to visualize user performance and task completion rates.}
        \resumeItem{Integrated a real-time AI Chatbot utilizing the \textbf{DeepSeek-R1 API} to provide instant user support and workflow guidance directly within the application.}
      \resumeItemListEnd

  \resumeSubHeadingListEnd

  

%-----------PROJECTS-----------

%-----------PROJECTS-----------

\section{PROJECTS}
  \resumeSubHeadingListStart

  

    \resumeProjectHeading
      {\textbf{Bank \& ATM Geographic Management System} -- \href{https://github.com/thanhnguyen221/BankAutoTest}{\color{blue} link} $|$ \emph{Django, PostgreSQL, GIS Mapping}}{Jan. 2025 -- Feb. 2025}
      \resumeItemListStart
            \resumeItem{Developed a role-based geographic management web application allowing administrators to visualize spatial distributions and monitor real-time ATM operational statuses.}
            \resumeItem{Engineered a hierarchical relational database schema (Bank-Branch-ATM) using \textbf{Django ORM}, utilizing abstract base classes to ensure a clean, \textbf{DRY architecture}.}
            \resumeItem{Optimized spatial query performance and map rendering speeds by implementing strategic \textbf{database indexing} on geographic coordinates and highly queried fields.}
            \resumeItem{Implemented secure user authentication workflows featuring advanced session management, strict \textbf{CSRF protection}, and safeguards against \textbf{Open Redirect} vulnerabilities.}
      \resumeItemListEnd

    \resumeProjectHeading
      {\textbf{Nova AI } -- \href{https://github.com/thanhnguyen221/nova-ai}{\color{blue} link} $|$ \emph{Django, SQLite, Gemini AI, Selenium, WebSocket}}{Mar. 2026 }
      \resumeItemListStart
            \resumeItem{Developed a custom AI chatbot using \textbf{Django} and \textbf{Google Gemini API}, enabling multi-turn conversations with streaming responses via Server-Sent Events and file attachments (PDF, TXT, DOCX).}
            \resumeItem{Built \textbf{Notebook LLM system} for importing URLs and documents; implemented \textbf{Selenium WebDriver} to crawl/scrape data from JavaScript-heavy websites with auto-click pagination and screenshot capture for knowledge-grounded AI responses.}
            \resumeItem{Created \textbf{Mindmap AI generator} that transforms imported sources into interactive SVG mindmaps with zoom/pan controls and node editing capabilities.}
            \resumeItem{Designed \textbf{Artifacts Panel} for live code/content preview (Claude AI-style) with split-view mode, fullscreen toggle, and real-time editing capabilities.}
            \resumeItem{Implemented \textbf{slide generation module} using \textbf{python-pptx} and \textbf{Playwright} for PPTX/PDF export, supporting 10+ layouts and 6 customizable themes.}
            \resumeItem{Integrated \textbf{PayOS payment gateway} for Pro subscription management with webhook handling and automated expiry tracking via Django signals.}
      \resumeItemListEnd

  \resumeSubHeadingListEnd


%-----------Skills-----------
\section{SKILLS}
  \resumeSubHeadingListStart
          \resumeProjectHeading{\textbf{English}}
    
        \resumeItemListStart
    
            \resumeItem{TOEIC 775/990 (Reading \& Listening)}
        \resumeItemListEnd
        
      \resumeProjectHeading{\textbf{Languages \& Programming}}
    
        \resumeItemListStart
            \resumeItem{Python, C++, SQL, ASP.NET}
        \resumeItemListEnd


      \resumeProjectHeading{\textbf{Frameworks \& Libraries}}
    
        \resumeItemListStart
            \resumeItem{Django, Flask, Django REST Framework, python-pptx, Selenium}
        \resumeItemListEnd


      \resumeProjectHeading{\textbf{Databases}}
    
        \resumeItemListStart
            \resumeItem{SQLite, SQL, MongoDB}
        \resumeItemListEnd

      \resumeProjectHeading{\textbf{Real-time \& Communication}}
    
        \resumeItemListStart
            \resumeItem{WebSocket, Server-Sent Events (SSE)}
        \resumeItemListEnd

      \resumeProjectHeading{\textbf{AI \& External APIs}}
    
        \resumeItemListStart
            \resumeItem{Google Gemini API, DeepSeek-R1 API, PayOS Payment Gateway}
        \resumeItemListEnd


        
 

        \resumeItemListEnd
    
  \resumeSubHeadingListEnd




\section{REFERENCES}
\textbf{Assoc. Prof. Nguyen Thanh Binh}, Head of the Department of Computer Science, Faculty of Mathematics and Computer Science, the University of Science - VNUHCM, email: \textbf{ngtbinh@hcmus.edu.vn}
%-------------------------------------------
\end{document}

